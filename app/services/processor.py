import asyncio, logging, random
from datetime import timedelta
from sqlalchemy import select, or_
from app.config import get_settings
from app.db import SessionLocal
from app.models import Job, Ticket, now_utc
from app.services.knowledge import search_articles
from app.services.ai import generate_draft
logger=logging.getLogger(__name__)
async def claim_job(job_id: int | None = None):
    cfg=get_settings()
    async with SessionLocal() as s:
        now=now_utc()
        q=select(Job).where(or_((Job.status=="queued")&(Job.available_at<=now),
          (Job.status=="processing")&(Job.lease_until<now))).order_by(Job.id).with_for_update(skip_locked=True).limit(1)
        if job_id is not None:q=q.where(Job.id==job_id)
        job=await s.scalar(q)
        if not job:return None
        job.status="processing";job.attempts+=1;job.lease_until=now+timedelta(seconds=cfg.worker_lease_seconds)
        ticket=await s.get(Ticket,job.ticket_id);ticket.status="Processing";ticket.attempts=job.attempts
        await s.commit();return job.id
async def process_job(job_id:int):
    cfg=get_settings()
    async with SessionLocal() as s:
        job=await s.get(Job,job_id);ticket=await s.get(Ticket,job.ticket_id)
        try:
            articles=await search_articles(s,ticket.message)
            result=await generate_draft(ticket.message,articles,s)
            ticket.draft=result.draft;ticket.sources=result.sources;ticket.confidence=result.confidence
            ticket.status="Draft Ready";ticket.last_error=None;job.status="done";job.lease_until=None
        except Exception as exc:
            logger.exception("Job %s failed",job_id);job.last_error=str(exc)[:2000];ticket.last_error=str(exc)[:2000]
            if job.attempts>=cfg.worker_max_attempts:job.status="failed";ticket.status="Failed"
            else:job.status="queued";job.available_at=now_utc()+timedelta(seconds=min(300,2**job.attempts+random.random()*2))
            job.lease_until=None
        await s.commit()
        return job.status in {"done","failed"}
async def run_worker():
    while True:
        job_id=await claim_job()
        if job_id is None:await asyncio.sleep(get_settings().worker_poll_seconds)
        else:await process_job(job_id)
