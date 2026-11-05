import pytest
from app.schemas import HelpdeskEvent
from app.services.helpdesk import validate_reply_url
from app.config import get_settings

def test_event_schema_accepts_and_rejects():
    event=HelpdeskEvent(event_id="evt-1",ticket_id="T-1",customer_email="a@example.com",message="PDF export fails",reply_url="http://mock-helpdesk/tickets/T-1/replies")
    assert event.ticket_id=="T-1"
    with pytest.raises(Exception):
        HelpdeskEvent(event_id="",ticket_id="T",customer_email="bad",message="",reply_url="file:///etc/passwd")

def test_reply_url_blocks_ssrf():
    with pytest.raises(ValueError):validate_reply_url("http://169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError):validate_reply_url("https://user:pass@mock-helpdesk/path")

@pytest.mark.asyncio
async def test_health_and_webhook_duplicate():
    from httpx import ASGITransport,AsyncClient
    from app.main import app
    from app.db import engine
    from app.models import Base
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    transport=ASGITransport(app=app)
    body={"event_id":"evt-test","ticket_id":"T-1","customer_email":"a@example.com","message":"PDF export error","reply_url":"http://mock-helpdesk/tickets/T-1/replies"}
    async with AsyncClient(transport=transport,base_url="http://test") as client:
        assert (await client.get("/health")).json()=={"status":"ok"}
        one=await client.post("/webhooks/helpdesk",json=body);two=await client.post("/webhooks/helpdesk",json=body)
        assert one.status_code==two.status_code==200
        assert two.json()["duplicate"] is True
    await engine.dispose()

@pytest.mark.asyncio
async def test_fallback_schema_and_delay(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from app.services import ai
    monkeypatch.setattr(ai,"acquire_global_slot",lambda *a,**k:asyncio.sleep(0))
    # Provider probe failure is tolerated; patch the HTTP client to avoid network.
    class Response:
        status_code=401
    class Client:
        def __init__(self,*a,**k):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def get(self,*a,**k):return Response()
    monkeypatch.setattr("httpx.AsyncClient",Client)
    delays=[]
    async def sleep(seconds):delays.append(seconds)
    monkeypatch.setattr(ai.asyncio,"sleep",sleep)
    monkeypatch.setenv("OPENAI_API_KEY","")
    get_settings.cache_clear()
    class Session:pass
    article=SimpleNamespace(id="kb_005",title="PDF Export",url="/knowledge/kb_005",content="Select Export then PDF.")
    result=await ai.generate_draft("PDF report", [article], Session())
    assert result.requires_human_review and result.sources[0]["article_id"]=="kb_005"
    assert delays==[5]

@pytest.mark.asyncio
async def test_concurrent_duplicate_delivery_creates_single_queue_job():
    import asyncio
    from httpx import ASGITransport,AsyncClient
    from sqlalchemy import select,func
    from app.main import app
    from app.db import engine,SessionLocal
    from app.models import Base,Job,Ticket
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    body={"event_id":"evt-concurrent","ticket_id":"T-CONCURRENT","customer_email":"parallel@example.com","message":"PDF export failed","reply_url":"http://mock-helpdesk/tickets/T-CONCURRENT/replies"}
    transport=ASGITransport(app=app)
    async with AsyncClient(transport=transport,base_url="http://test") as client:
        first,second=await asyncio.gather(client.post("/webhooks/helpdesk",json=body),client.post("/webhooks/helpdesk",json=body))
    assert first.status_code==second.status_code==200
    async with SessionLocal() as session:
        count=await session.scalar(select(func.count()).select_from(Job).join(Ticket).where(Ticket.event_id=="evt-concurrent"))
        assert count==1
