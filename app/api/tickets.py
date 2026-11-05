from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.db import get_session
from app.models import Ticket,Outbox,now_utc
from app.services.helpdesk import send_reply
from app.security import require_operator
from app.config import get_settings
router=APIRouter(tags=["tickets"])
@router.get("/api/tickets")
async def tickets(_:None=Depends(require_operator),session:AsyncSession=Depends(get_session)):
    return (await session.scalars(select(Ticket).order_by(Ticket.created_at.desc()))).all()
@router.post("/tickets/{ticket_pk}/approve")
async def approve(ticket_pk:int,_:None=Depends(require_operator),session:AsyncSession=Depends(get_session)):
    async with session.begin():
        ticket=await session.scalar(select(Ticket).where(Ticket.id==ticket_pk).with_for_update())
        if not ticket:raise HTTPException(404,"Ticket not found")
        if ticket.status in {"Sending","Sent"}:return {"status":ticket.status}
        if ticket.status!="Draft Ready" or not ticket.draft:raise HTTPException(409,"Draft is not ready")
        ticket.status="Approved"
        insert_fn=pg_insert if session.get_bind().dialect.name=="postgresql" else sqlite_insert
        await session.execute(insert_fn(Outbox).values(ticket_id=ticket.id,idempotency_key="reply-"+ticket.event_id,status="pending").on_conflict_do_nothing(index_elements=[Outbox.ticket_id]))
    await deliver_outbox(ticket_pk,session)
    return {"status":ticket.status}
@router.post("/tickets/{ticket_pk}/reject")
async def reject(ticket_pk:int,_:None=Depends(require_operator),session:AsyncSession=Depends(get_session)):
    ticket=await session.get(Ticket,ticket_pk)
    if not ticket:raise HTTPException(404,"Ticket not found")
    if ticket.status!="Draft Ready":raise HTTPException(409,"Draft is not ready")
    ticket.status="Rejected";await session.commit()
    return {"status":ticket.status}
@router.post("/tickets/{ticket_pk}/edit")
async def edit(ticket_pk:int,draft:str=Form(...),_:None=Depends(require_operator),session:AsyncSession=Depends(get_session)):
    ticket=await session.get(Ticket,ticket_pk)
    if not ticket:raise HTTPException(404,"Ticket not found")
    if ticket.status!="Draft Ready":raise HTTPException(409,"Draft is not editable")
    ticket.draft=draft[:10000];await session.commit()
    return RedirectResponse("/",303)
async def deliver_outbox(ticket_pk:int,session:AsyncSession):
    async with session.begin():
        ticket=await session.scalar(select(Ticket).where(Ticket.id==ticket_pk).with_for_update())
        outbox=await session.scalar(select(Outbox).where(Outbox.ticket_id==ticket_pk).with_for_update())
        if not ticket or not outbox or outbox.status=="sent":return
        now=now_utc()
        if outbox.status=="sending" and outbox.lease_until and outbox.lease_until>now:return
        if outbox.status=="pending" and outbox.available_at>now:return
        outbox.status="sending";outbox.lease_until=now+timedelta(seconds=45);ticket.status="Sending"
        reply_url,ticket_id,draft,key=ticket.reply_url,ticket.ticket_id,ticket.draft,outbox.idempotency_key
    try:
        await send_reply(reply_url,ticket_id,draft,key)
    except Exception as exc:
        async with session.begin():
            outbox=await session.scalar(select(Outbox).where(Outbox.ticket_id==ticket_pk).with_for_update())
            ticket=await session.scalar(select(Ticket).where(Ticket.id==ticket_pk).with_for_update())
            outbox.attempts+=1;outbox.last_error=str(exc)[:2000]
            outbox.available_at=now_utc()+timedelta(seconds=min(300,2**outbox.attempts))
            outbox.status="pending" if outbox.attempts<get_settings().worker_max_attempts else "failed";outbox.lease_until=None
            ticket.status="Failed";ticket.last_error=outbox.last_error
        return
    async with session.begin():
        outbox=await session.scalar(select(Outbox).where(Outbox.ticket_id==ticket_pk).with_for_update())
        ticket=await session.scalar(select(Ticket).where(Ticket.id==ticket_pk).with_for_update())
        outbox.status="sent";outbox.lease_until=None;outbox.last_error=None
        ticket.status="Sent";ticket.last_error=None
