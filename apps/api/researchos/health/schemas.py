"""DTOs for the health/readiness endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "error"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "researchos-api"
    version: str


class DependencyCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: CheckStatus
    checks: list[DependencyCheck]
