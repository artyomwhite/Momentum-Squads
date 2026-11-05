from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.config import get_settings
from app.db import engine
from app.models import Base
from app.api import health,webhooks,tickets,knowledge,operator
@asynccontextmanager
async def lifespan(app:FastAPI):
    if get_settings().database_url.startswith("sqlite"):
        async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
app=FastAPI(title="Momentum Support Desk",lifespan=lifespan)
app.add_middleware(SessionMiddleware,secret_key=get_settings().session_secret,same_site="lax",https_only=bool(__import__("os").getenv("VERCEL")))
app.mount("/static",StaticFiles(directory="app/static"),name="static")
app.include_router(health.router);app.include_router(webhooks.router);app.include_router(tickets.router);app.include_router(knowledge.router);app.include_router(operator.router)
