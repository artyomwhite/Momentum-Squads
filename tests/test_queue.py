from types import SimpleNamespace
import pytest
from app import queues

@pytest.mark.asyncio
async def test_queue_publisher_uses_stable_job_key(monkeypatch):
    sent=[]
    async def fake_send(topic,payload,**kwargs):sent.append((payload.model_dump(),kwargs))
    monkeypatch.setattr(queues,"send",fake_send)
    await queues.publish_job(42)
    assert sent[0][0]=={"kind":"draft","record_id":42}
    assert sent[0][2]["idempotency_key"]=="draft-42" and sent[0][0]["record_id"]==42

@pytest.mark.asyncio
async def test_queue_handler_claims_and_processes_job(monkeypatch):
    claimed=[]
    async def claim(job_id):claimed.append(job_id);return job_id
    async def process(job_id):return True
    monkeypatch.setattr(queues,"claim_job",claim)
    monkeypatch.setattr(queues,"process_job",process)
    await queues.handle_work(SimpleNamespace(payload=queues.WorkItem(kind="draft",record_id=7)))
    assert claimed==[7]

@pytest.mark.asyncio
async def test_queue_handler_retries_rescheduled_job(monkeypatch):
    async def claim(job_id):return job_id
    async def process(job_id):return False
    async def delay(job_id):return 12
    monkeypatch.setattr(queues,"claim_job",claim)
    monkeypatch.setattr(queues,"process_job",process)
    monkeypatch.setattr(queues,"_retry_after_job",delay)
    with pytest.raises(queues.RetryAfter):await queues.handle_work(SimpleNamespace(payload=queues.WorkItem(kind="draft",record_id=8)))
