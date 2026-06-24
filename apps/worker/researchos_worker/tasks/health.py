"""Worker health tasks.

These verify that the worker process is alive and can reach its infrastructure
dependencies. They reuse the async connectivity probes from the API package.
"""

from __future__ import annotations

from typing import Any

import structlog
from researchos.common.asyncio_runner import run_async_task
from researchos.common.db import check_db
from researchos.common.redis import check_redis

from ..app import app

logger = structlog.get_logger(__name__)


@app.task(name="health.ping")
def ping() -> str:
    """Trivial liveness task."""

    return "pong"


async def _check_dependencies() -> dict[str, Any]:
    results: dict[str, Any] = {"redis": "error", "postgres": "error"}
    try:
        await check_redis()
        results["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report any dependency failure
        logger.warning("worker_redis_check_failed", error=str(exc))
        results["redis_detail"] = str(exc)
    try:
        await check_db()
        results["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report any dependency failure
        logger.warning("worker_postgres_check_failed", error=str(exc))
        results["postgres_detail"] = str(exc)
    return results


@app.task(name="health.check_dependencies")
def check_dependencies() -> dict[str, Any]:
    """Probe Redis and PostgreSQL from within the worker process.

    Runs both probes in a single event loop and disposes loop-bound globals
    afterwards (see researchos.common.asyncio_runner).
    """

    return run_async_task(_check_dependencies)
