import asyncio,logging
from sqlalchemy import select,or_
from app.db import SessionLocal
from app.models import Outbox,now_utc
from app.services.processor import claim_job,process_job
from app.api.tickets import deliver_outbox
from app.config import get_settings
logging.basicConfig(level=logging.INFO)
async def consume():
    while True:
        try:
            job=await claim_job()
            if job is not None:
                await process_job(job);continue
            async with SessionLocal() as s:
                ticket_pk=await s.scalar(select(Outbox.ticket_id).where(or_((Outbox.status=="pending")&(Outbox.available_at<=now_utc()),(Outbox.status=="sending")&(Outbox.lease_until<now_utc()))).order_by(Outbox.id).limit(1))
            if ticket_pk is not None:
                async with SessionLocal() as delivery_session:await deliver_outbox(ticket_pk,delivery_session)
                continue
        except Exception:
            logging.exception("Worker loop failed; retrying")
        await asyncio.sleep(get_settings().worker_poll_seconds)
async def run():
    async with asyncio.TaskGroup() as group:
        for _ in range(max(1,get_settings().worker_concurrency)):group.create_task(consume())
if __name__=="__main__":asyncio.run(run())
