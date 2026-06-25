"""
Database Engine & Session Factory
Async SQLAlchemy 2.0 setup with connection pooling
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine() -> AsyncEngine:
    """Create and return the async SQLAlchemy engine."""
    kwargs: dict = {
        "echo": settings.db.ECHO_SQL,
        "pool_pre_ping": True,
    }

    if settings.ENVIRONMENT == "testing":
        # Use NullPool for tests to avoid connection issues
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = settings.db.POOL_SIZE
        kwargs["max_overflow"] = settings.db.MAX_OVERFLOW
        kwargs["pool_timeout"] = settings.db.POOL_TIMEOUT
        kwargs["pool_recycle"] = 1800

    return create_async_engine(settings.db.DATABASE_URL, **kwargs)


def get_engine() -> AsyncEngine:
    """Get the singleton engine, creating it if necessary."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the singleton session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides a transactional database session.
    Commits on success, rolls back on exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
    Usage: session: AsyncSession = Depends(get_session)
    """
    async with get_db_session() as session:
        yield session


async def close_engine() -> None:
    """Gracefully dispose the database engine."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine closed")


async def check_db_connection() -> bool:
    """Health check — returns True if the DB is reachable."""
    from sqlalchemy import text

    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc))
        return False
