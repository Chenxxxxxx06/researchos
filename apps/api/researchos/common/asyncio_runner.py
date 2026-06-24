"""Run an async coroutine in a fresh event loop with loop-bound cleanup.

Celery prefork workers invoke each task synchronously and we drive async code
with ``asyncio.run``, which creates and then closes a new event loop per task.
The process-global async SQLAlchemy engine/sessionmaker and the async Redis
client are bound to the event loop that created them. If they are reused by a
later task running on a different loop, asyncpg/redis fail with
``RuntimeError: Event loop is closed`` or
``RuntimeError: got Future attached to a different loop``.

``run_async_task`` disposes those globals at the end of every task (inside the
same loop, before it closes), so the next task recreates them cleanly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .db import dispose_engine
from .redis import close_redis

T = TypeVar("T")


def run_async_task(factory: Callable[[], Awaitable[T]]) -> T:
    """Run ``factory()`` to completion in a fresh loop, then dispose loop-bound globals."""

    async def _runner() -> T:
        try:
            return await factory()
        finally:
            await dispose_engine()
            await close_redis()

    return asyncio.run(_runner())
