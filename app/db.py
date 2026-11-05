import os
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from app.config import get_settings

database_url = make_url(get_settings().database_url)
connect_args = {}

# Neon commonly supplies PostgreSQL URLs with `sslmode=require`. SQLAlchemy's
# asyncpg dialect passes URL query parameters directly to asyncpg, which expects
# `ssl` instead of libpq's `sslmode` option.
query = dict(database_url.query)
sslmode = query.pop("sslmode", None)
if sslmode == "require":
    query.setdefault("ssl", "require")
    connect_args["ssl"] = "require"
database_url = database_url.set(query=query)

engine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    **({"poolclass": NullPool} if os.getenv("VERCEL") else {"pool_size": 5, "max_overflow": 5}),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    async with SessionLocal() as session:
        yield session
