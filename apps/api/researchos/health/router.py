"""Health and readiness endpoints.

``/healthz`` is a pure liveness check (no external dependencies) suitable for
container liveness probes. ``/readyz`` probes PostgreSQL, Redis, and object
storage, and returns 503 if any dependency is unavailable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter, Response, status

from researchos import __version__
from researchos.common.db import check_db
from researchos.common.redis import check_redis
from researchos.common.storage import check_object_storage

from .schemas import DependencyCheck, HealthResponse, ReadinessResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

# Name -> async probe. Each probe raises on failure.
_PROBES: dict[str, Callable[[], Awaitable[None]]] = {
    "postgres": check_db,
    "redis": check_redis,
    "object_storage": check_object_storage,
}


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness check — the process is up and serving."""

    return HealthResponse(version=__version__)


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(response: Response) -> ReadinessResponse:
    """Readiness check — required dependencies are reachable."""

    checks: list[DependencyCheck] = []
    all_ok = True

    for name, probe in _PROBES.items():
        try:
            await probe()
            checks.append(DependencyCheck(name=name, status="ok"))
        except Exception as exc:  # noqa: BLE001 - report any dependency failure
            all_ok = False
            logger.warning("readiness_check_failed", dependency=name, error=str(exc))
            checks.append(DependencyCheck(name=name, status="error", detail=str(exc)))

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(status="ok" if all_ok else "error", checks=checks)
