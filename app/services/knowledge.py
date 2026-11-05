from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Article
async def search_articles(session: AsyncSession, query: str, limit: int=4) -> list[Article]:
    if session.get_bind().dialect.name == "postgresql":
        rows=await session.execute(text("""
            SELECT id, ts_rank(to_tsvector('simple', title || ' ' || content),
             plainto_tsquery('simple', :query)) rank FROM articles
            WHERE to_tsvector('simple', title || ' ' || content) @@ plainto_tsquery('simple', :query)
            ORDER BY rank DESC LIMIT :limit
        """),{"query":query[:1000],"limit":limit})
        ids=[r.id for r in rows]
        if ids:
            articles=(await session.scalars(select(Article).where(Article.id.in_(ids)))).all()
            order={v:i for i,v in enumerate(ids)}
            return sorted(articles,key=lambda a:order[a.id])
    tokens={x.casefold() for x in query.split() if len(x)>2}
    articles=(await session.scalars(select(Article))).all()
    ranked=[(sum((a.title+" "+a.content).casefold().count(t) for t in tokens),a) for a in articles]
    return [a for score,a in sorted(ranked,key=lambda x:x[0],reverse=True)[:limit] if score]
