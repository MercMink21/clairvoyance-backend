from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Managed Postgres providers (Railway, Render, Heroku, Fly) hand out a
    ``postgres://`` or ``postgresql://`` URL, but this app's async engine needs
    the ``postgresql+asyncpg://`` driver form. Normalize so the raw provider
    URL can be dropped straight into DATABASE_URL without hand-editing."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


engine = create_async_engine(
    _normalize_db_url(settings.DATABASE_URL),
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
