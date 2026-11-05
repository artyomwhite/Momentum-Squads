from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import Ticket,Job
from app.schemas import HelpdeskEvent
from app.services.helpdesk import validate_reply_url
router=APIRouter(prefix="/webhooks",tags=["webhooks"])
@router.post("/helpdesk",status_code=200)
async def receive(event:HelpdeskEvent,session:AsyncSession=Depends(get_session)):
    try:url=validate_reply_url(event.reply_url)
    except ValueError as exc:raise HTTPException(422,str(exc))
    async with session.begin():
        insert_fn=pg_insert if session.get_bind().dialect.name=="postgresql" else sqlite_insert
        stmt=insert_fn(Ticket).values(event_id=event.event_id,ticket_id=event.ticket_id,
          customer_email=str(event.customer_email),message=event.message,reply_url=url,status="Received",sources=[])
        stmt=stmt.on_conflict_do_nothing(index_elements=[Ticket.event_id]).returning(Ticket.id)
        new_id=await session.scalar(stmt)
        if new_id is not None:session.add(Job(ticket_id=new_id))
    return {"status":"accepted","duplicate":new_id is None}
