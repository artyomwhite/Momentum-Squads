from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
router=APIRouter(tags=["health"])
@router.get("/health")
async def health():return {"status":"ok"}
@router.get("/ready")
async def ready(session:AsyncSession=Depends(get_session)):
    try:await session.execute(text("SELECT 1"))
    except Exception as exc:raise HTTPException(503,"database unavailable") from exc
    return {"status":"ready"}
