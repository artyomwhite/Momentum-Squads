from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import Article
from app.services.knowledge import search_articles
router=APIRouter(prefix="/knowledge",tags=["knowledge"])
@router.get("")
async def list_articles(session:AsyncSession=Depends(get_session)):
    return (await session.scalars(select(Article).order_by(Article.category,Article.title))).all()
@router.get("/search")
async def search(q:str,session:AsyncSession=Depends(get_session)):
    return await search_articles(session,q)
@router.get("/{article_id}")
async def article(article_id:str,session:AsyncSession=Depends(get_session)):
    row=await session.get(Article,article_id)
    if not row:raise HTTPException(404,"Article not found")
    return row
