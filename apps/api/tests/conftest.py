"""Test fixtures for the ResearchOS API.

Integration tests run against the real PostgreSQL and Redis from the local
Docker stack, but use a dedicated test database (``researchos_test``) and Redis
DB index 15 so developer data is never touched.

Environment variables are set at import time, before any application module
(and therefore ``Settings``) is imported.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

# --- Test environment (must be set before importing the app) -----------------
os.environ.setdefault(
    "POSTGRES_DSN",
    "postgresql+asyncpg://researchos:researchos@localhost:5432/researchos_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENVIRONMENT", "local")
# Each test runs in its own event loop; a non-pooling engine avoids reusing a
# connection bound to a closed loop.
os.environ.setdefault("DB_USE_NULLPOOL", "true")
# Isolated workspace root for IDE tests.
os.environ.setdefault("WORKSPACE_ROOT", tempfile.mkdtemp(prefix="ros-ws-test-"))

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

import researchos.models as models  # noqa: E402
from researchos.common.config import get_settings  # noqa: E402
from researchos.common.db import dispose_engine, get_engine  # noqa: E402
from researchos.common.redis import close_redis, get_redis  # noqa: E402
from researchos.main import create_app  # noqa: E402

_TABLES = [
    "skill_installations",
    "skill_versions",
    "skills",
    "latex_compile_jobs",
    "document_files",
    "latex_projects",
    "experiment_artifacts",
    "experiment_logs",
    "experiment_metrics",
    "experiment_runs",
    "experiments",
    "patch_hunks",
    "patch_files",
    "patch_proposals",
    "agent_run_events",
    "tool_calls",
    "research_critiques",
    "agent_runs",
    "ideas",
    "papers",
    "project_memberships",
    "projects",
    "organization_memberships",
    "organizations",
    "users",
]


async def _ensure_database() -> None:
    """Create the test database (if missing) and (re)create all tables."""

    dsn = get_settings().postgres_dsn
    base, dbname = dsn.rsplit("/", 1)
    maint_engine = create_async_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT")
    async with maint_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    await maint_engine.dispose()

    engine = create_async_engine(dsn)
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _setup_database() -> None:
    asyncio.run(_ensure_database())


@pytest_asyncio.fixture(autouse=True)
async def _isolate() -> AsyncIterator[None]:
    """Truncate tables and flush the test Redis DB around each test.

    Also disposes the app's engine/redis client at the end so the next test
    recreates them in its own event loop.
    """

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))
    await get_redis().flushdb()
    # Reset the global engine/redis client so each test starts from an unbound
    # state. This matters for synchronous tests that spawn their own event loops
    # (e.g. the worker-task regression test), which would otherwise reuse globals
    # bound to the fixture's event loop.
    await dispose_engine()
    await close_redis()
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A database session sharing the app engine (for service/runtime tests)."""

    from researchos.common.db import get_sessionmaker

    async with get_sessionmaker()() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """An unauthenticated HTTP client bound to the ASGI app (own cookie jar)."""

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
def make_client():
    """Factory returning fresh clients (separate cookie jars) for multi-user tests."""

    app = create_app()
    transport = ASGITransport(app=app)
    created: list[AsyncClient] = []

    def _factory() -> AsyncClient:
        ac = AsyncClient(transport=transport, base_url="http://testserver")
        created.append(ac)
        return ac

    yield _factory
