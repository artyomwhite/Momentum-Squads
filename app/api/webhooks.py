import os,logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import Ticket,Job
from app.schemas import HelpdeskEvent
from app.services.helpdesk import validate_reply_url
from sqlalchemy import select
router=APIRouter(prefix="/webhooks",tags=["webhooks"])
logger=logging.getLogger(__name__)
@router.post("/helpdesk",status_code=200)
async def receive(event:HelpdeskEvent,session:AsyncSession=Depends(get_session)):
    try:url=validate_reply_url(event.reply_url)
    except ValueError as exc:raise HTTPException(422,str(exc))
    job_id=None
    async with session.begin():
        insert_fn=pg_insert if session.get_bind().dialect.name=="postgresql" else sqlite_insert
        stmt=insert_fn(Ticket).values(event_id=event.event_id,ticket_id=event.ticket_id,
          customer_email=str(event.customer_email),message=event.message,reply_url=url,status="Received",sources=[])
        stmt=stmt.on_conflict_do_nothing(index_elements=[Ticket.event_id]).returning(Ticket.id)
        new_id=await session.scalar(stmt)
        if new_id is not None:
            job=Job(ticket_id=new_id);session.add(job);await session.flush();job_id=job.id
        else:
            ticket=await session.scalar(select(Ticket).where(Ticket.event_id==event.event_id))
            job_id=await session.scalar(select(Job.id).where(Job.ticket_id==ticket.id)) if ticket else None
    if os.getenv("VERCEL") and job_id is not None:
        try:
            from app.queues import publish_job
            await publish_job(job_id)
        except Exception as exc:
            logger.exception("Could not publish the durable job; caller should retry")
            raise HTTPException(503,"Queue is temporarily unavailable; retry this event") from exc
    return {"status":"accepted","duplicate":new_id is None}
