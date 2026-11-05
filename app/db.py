import os
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from app.config import get_settings
engine = create_async_engine(get_settings().database_url, pool_pre_ping=True, **({"poolclass": NullPool} if os.getenv("VERCEL") else {"pool_size": 5, "max_overflow": 5}))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
async def get_session():
    async with SessionLocal() as session:
        yield session
