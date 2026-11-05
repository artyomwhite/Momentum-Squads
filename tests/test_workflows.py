import pytest
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.models import Base,Ticket,Job,Outbox,now_utc
from app.services.processor import claim_job

@pytest.mark.asyncio
async def test_expired_job_lease_is_reclaimed():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async with factory() as session:
        ticket=Ticket(event_id="evt-recover",ticket_id="T-R",customer_email="r@example.com",message="Help",reply_url="http://mock-helpdesk/replies",status="Processing",sources=[])
        session.add(ticket);await session.flush()
        job=Job(ticket_id=ticket.id,status="processing",attempts=1,lease_until=now_utc()-timedelta(seconds=10))
        session.add(job);await session.commit();job_id=job.id
    from app.services import processor
    old=processor.SessionLocal;processor.SessionLocal=factory
    try:
        claimed=await claim_job()
        assert claimed==job_id
        async with factory() as session:
            job=await session.get(Job,job_id)
            assert job.status=="processing" and job.attempts==2
    finally:
        processor.SessionLocal=old
        await engine.dispose()

@pytest.mark.asyncio
async def test_operator_approval_creates_outbox_then_sends(monkeypatch):
    from httpx import ASGITransport,AsyncClient
    from app.main import app
    from app.db import engine,SessionLocal
    from app.api import tickets as ticket_routes
    from app.config import get_settings
    from sqlalchemy import select
    from app.models import Base
    monkeypatch.setenv("OPERATOR_USERNAME","operator")
    monkeypatch.setenv("OPERATOR_PASSWORD","secret")
    get_settings.cache_clear()
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        ticket=Ticket(event_id="evt-approve",ticket_id="T-A",customer_email="a@example.com",message="Question",reply_url="http://mock-helpdesk/replies",status="Draft Ready",draft="Reviewed answer",sources=[])
        session.add(ticket);await session.commit();pk=ticket.id
    sent=[]
    async def fake_send(url,ticket_id,message,key):sent.append((ticket_id,message,key))
    monkeypatch.setattr(ticket_routes,"send_reply",fake_send)
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        assert (await client.get("/api/tickets")).status_code==401
        login=await client.post("/login",data={"username":"operator","password":"secret"})
        assert login.status_code==303
        result=await client.post(f"/tickets/{pk}/approve")
        assert result.status_code==200 and result.json()["status"]=="Sent"
        duplicate=await client.post(f"/tickets/{pk}/approve")
        assert duplicate.json()["status"]=="Sent"
    assert len(sent)==1 and sent[0][2]=="reply-evt-approve"
    async with SessionLocal() as session:
        saved=await session.get(Ticket,pk)
        outbox=await session.scalar(select(Outbox).where(Outbox.ticket_id==pk))
        assert saved.status=="Sent" and outbox.status=="sent"
    get_settings.cache_clear()

@pytest.mark.asyncio
async def test_operator_reject_does_not_send():
    from httpx import ASGITransport,AsyncClient
    from app.main import app
    from app.db import engine,SessionLocal
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        ticket=Ticket(event_id="evt-reject",ticket_id="T-X",customer_email="x@example.com",message="Question",reply_url="http://mock-helpdesk/replies",status="Draft Ready",draft="Draft",sources=[])
        session.add(ticket);await session.commit();pk=ticket.id
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        await client.post("/login",data={"username":"operator","password":"change-me"})
        response=await client.post(f"/tickets/{pk}/reject")
        assert response.json()=={"status":"Rejected"}
    async with SessionLocal() as session:
        saved=await session.get(Ticket,pk)
        outbox=await session.scalar(select(Outbox).where(Outbox.ticket_id==pk))
        assert saved.status=="Rejected" and outbox is None

@pytest.mark.asyncio
async def test_helpdesk_failure_is_retryable_from_outbox(monkeypatch):
    from app.db import engine,SessionLocal
    from app.api.tickets import deliver_outbox
    from app.models import Base
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        ticket=Ticket(event_id="evt-fail",ticket_id="T-F",customer_email="f@example.com",message="Question",reply_url="http://mock-helpdesk/replies",status="Approved",draft="Answer",sources=[])
        session.add(ticket);await session.flush()
        record=Outbox(ticket_id=ticket.id,idempotency_key="reply-evt-fail",status="pending")
        session.add(record);await session.commit();pk=ticket.id
    async def fail(*args,**kwargs):raise RuntimeError("simulated 500")
    monkeypatch.setattr("app.api.tickets.send_reply",fail)
    async with SessionLocal() as session:await deliver_outbox(pk,session)
    async with SessionLocal() as session:
        record=await session.scalar(select(Outbox).where(Outbox.ticket_id==pk))
        ticket=await session.get(Ticket,pk)
        assert record.status=="pending" and record.attempts==1
        assert ticket.status=="Failed" and "simulated 500" in ticket.last_error
