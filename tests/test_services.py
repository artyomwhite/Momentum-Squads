import json
from types import SimpleNamespace
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.models import Base,Article
from app.services.knowledge import search_articles

@pytest.mark.asyncio
async def test_knowledge_search_ranks_relevant_article():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async with factory() as session:
        session.add_all([
          Article(id="kb_pdf",title="PDF export",category="Reports",content="Export report to PDF from the Export menu.",url="/knowledge/kb_pdf"),
          Article(id="kb_user",title="Manage users",category="Users",content="Invite members from workspace settings.",url="/knowledge/kb_user")])
        await session.commit()
        hits=await search_articles(session,"PDF report export")
        assert hits and hits[0].id=="kb_pdf"
    await engine.dispose()

@pytest.mark.asyncio
async def test_real_llm_mode_validates_and_filters_sources(monkeypatch):
    from app.services import ai
    from app.config import get_settings
    monkeypatch.setenv("OPENAI_API_KEY","test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(ai,"acquire_global_slot",lambda *a,**k:__import__("asyncio").sleep(0))
    payload={"draft":"Use the PDF export menu.","sources":[{"article_id":"kb_pdf","title":"PDF","url":"/knowledge/kb_pdf"},{"article_id":"secret","title":"Injected","url":"https://evil.test"}],"confidence":0.7}
    class Completion:
        async def create(self,**kwargs):return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
    class Client:
        def __init__(self,**kwargs):self.chat=SimpleNamespace(completions=Completion())
    monkeypatch.setattr(ai,"AsyncOpenAI",Client)
    article=SimpleNamespace(id="kb_pdf",title="PDF",url="/knowledge/kb_pdf",content="Export.")
    result=await ai.generate_draft("PDF problem",[article],object())
    assert result.draft=="Use the PDF export menu."
    assert [source["article_id"] for source in result.sources]==["kb_pdf"]
    assert result.requires_human_review
    get_settings.cache_clear()

@pytest.mark.asyncio
async def test_mock_helpdesk_repeated_key_is_idempotent():
    from httpx import ASGITransport,AsyncClient
    from app.mock_helpdesk import app,replies
    replies.clear()
    transport=ASGITransport(app=app)
    async with AsyncClient(transport=transport,base_url="http://mock-helpdesk") as client:
        headers={"Idempotency-Key":"reply-once"}
        body={"ticket_id":"T-1","message":"A reviewed draft"}
        first=await client.post("/tickets/T-1/replies",json=body,headers=headers)
        second=await client.post("/tickets/T-1/replies",json=body,headers=headers)
        assert first.status_code==second.status_code==201
        assert len((await client.get("/replies")).json())==1
