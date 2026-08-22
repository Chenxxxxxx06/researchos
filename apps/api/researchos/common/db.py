"""Database engine, session factory, and a connectivity probe.

Uses SQLAlchemy 2.0 async with asyncpg. Phase 0 only needs connectivity for the
readiness check; later phases add models and repositories.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""

    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict = {"echo": False, "future": True}
        if settings.db_use_nullpool:
            kwargs["poolclass"] = NullPool
        else:
            kwargs.update(
                pool_pre_ping=True,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_recycle=1800,
            )
        _engine = create_async_engine(settings.postgres_dsn, **kwargs)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a database session."""

    async with get_sessionmaker()() as session:
        yield session


async def check_db() -> None:
    """Raise if the database is unreachable (used by the readiness probe)."""

    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def warm_db_pool() -> int:
    """Open and validate the API's configured pool before serving traffic.

    Connections are held until the target count is reached; otherwise each
    iteration would just reuse the same returned connection. NullPool callers
    (tests and Celery workers) intentionally skip this optimization.
    """

    settings = get_settings()
    if settings.db_use_nullpool or settings.db_pool_size <= 0:
        return 0

    connections = []
    try:
        for _ in range(settings.db_pool_size):
            connection = await get_engine().connect()
            connections.append(connection)
            await connection.execute(text("SELECT 1"))
    finally:
        if connections:
            await asyncio.gather(*(connection.close() for connection in connections))
    return len(connections)


async def dispose_engine() -> None:
    """Dispose the engine on shutdown."""

    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _sessionmaker = None
