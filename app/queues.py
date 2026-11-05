from typing import Literal
from pydantic import BaseModel,Field
from sqlalchemy import select
from vercel.queue import Message,RetryAfter,Topic,send,subscribe
from app.db import SessionLocal
from app.models import Job,Outbox,now_utc
from app.services.processor import claim_job,process_job
from app.api.tickets import deliver_outbox

class WorkItem(BaseModel):
    kind:Literal["draft","delivery"]
    record_id:int=Field(gt=0)

work_items=Topic[WorkItem]("momentum-support-work")

async def publish_job(job_id:int):
    await send(work_items,WorkItem(kind="draft",record_id=job_id),idempotency_key=f"draft-{job_id}")

async def publish_delivery(ticket_id:int):
    await send(work_items,WorkItem(kind="delivery",record_id=ticket_id),idempotency_key=f"delivery-{ticket_id}")

async def _retry_after_job(job_id:int):
    async with SessionLocal() as session:
        job=await session.get(Job,job_id)
        if not job or job.status in {"done","failed"}:return None
        due=job.lease_until if job.status=="processing" else job.available_at
        if due is None:return 1
        now=now_utc()
        return max(1,min(600,int((due-now).total_seconds())+1))

async def _retry_after_delivery(ticket_id:int):
    async with SessionLocal() as session:
        outbox=await session.scalar(select(Outbox).where(Outbox.ticket_id==ticket_id))
        if not outbox or outbox.status in {"sent","failed"}:return None
        due=outbox.lease_until if outbox.status=="sending" else outbox.available_at
        if due is None:return 1
        return max(1,min(600,int((due-now_utc()).total_seconds())+1))

@subscribe(topic=work_items,consumer_group="momentum-support-worker")
async def handle_work(message:Message[WorkItem])->None:
    item=message.payload
    if item.kind=="draft":
        claimed=await claim_job(item.record_id)
        if claimed is None:
            delay=await _retry_after_job(item.record_id)
            if delay is not None:raise RetryAfter(delay)
            return
        if not await process_job(claimed):
            delay=await _retry_after_job(item.record_id)
            if delay is not None:raise RetryAfter(delay)
        return
    async with SessionLocal() as session:
        completed=await deliver_outbox(item.record_id,session)
    if not completed:
        delay=await _retry_after_delivery(item.record_id)
        if delay is not None:raise RetryAfter(delay)
