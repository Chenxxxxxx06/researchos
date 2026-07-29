"""Project-scoped venue deadline endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from researchos.common.deps import CurrentUser, DbSession
from researchos.projects.service import ProjectService

from .schemas import VenueDeadlineFeed
from .service import VenueDeadlineService

router = APIRouter(prefix="/projects/{project_id}/venues", tags=["venues"])


@router.get("/deadlines", response_model=VenueDeadlineFeed)
async def list_deadlines(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> VenueDeadlineFeed:
    await ProjectService(db).ensure_access(user, project_id)
    return await VenueDeadlineService().fetch()
