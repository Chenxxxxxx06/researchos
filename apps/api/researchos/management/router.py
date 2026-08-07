"""Unified management-center endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from researchos.common.deps import CurrentUser, DbSession

from .schemas import ManagementSummaryResponse
from .service import ManagementService

router = APIRouter(prefix="/projects/{project_id}/manage", tags=["management"])


@router.get("/summary", response_model=ManagementSummaryResponse)
async def summary(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ManagementSummaryResponse:
    return ManagementSummaryResponse.model_validate(
        await ManagementService(db).summary(user, project_id)
    )
