"""Git status endpoint (read-only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from researchos.common.deps import CurrentUser, DbSession

from .schemas import GitStatusResponse
from .service import GitService

router = APIRouter(prefix="/projects/{project_id}/git", tags=["git"])


@router.get("/status", response_model=GitStatusResponse)
async def git_status(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GitStatusResponse:
    return await GitService(db).status(user, project_id)
