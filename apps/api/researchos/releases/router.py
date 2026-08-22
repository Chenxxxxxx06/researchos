"""Release Studio routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import CreateReleaseJobRequest, ReleaseIntegrationStatus, ReleaseJobResponse
from .service import ReleaseService

router = APIRouter(prefix="/projects/{project_id}/releases", tags=["releases"])


@router.get("/integration", response_model=ReleaseIntegrationStatus)
async def integration_status(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ReleaseIntegrationStatus:
    return await ReleaseService(db).integration_status(user, project_id)


@router.get("", response_model=list[ReleaseJobResponse])
async def list_release_jobs(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ReleaseJobResponse]:
    jobs = await ReleaseService(db).list_jobs(user, project_id, limit=limit)
    return [ReleaseJobResponse.model_validate(job) for job in jobs]


@router.post(
    "",
    response_model=ReleaseJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_release_job(
    project_id: uuid.UUID,
    payload: CreateReleaseJobRequest,
    user: CurrentUser,
    db: DbSession,
) -> ReleaseJobResponse:
    job = await ReleaseService(db).create_job(user, project_id, payload)
    return ReleaseJobResponse.model_validate(job)


@router.get("/{job_id}", response_model=ReleaseJobResponse)
async def get_release_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> ReleaseJobResponse:
    job = await ReleaseService(db).get_job(user, project_id, job_id)
    return ReleaseJobResponse.model_validate(job)


@router.post(
    "/{job_id}/cancel",
    response_model=ReleaseJobResponse,
    dependencies=[Depends(require_csrf)],
)
async def cancel_release_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> ReleaseJobResponse:
    job = await ReleaseService(db).cancel_job(user, project_id, job_id)
    return ReleaseJobResponse.model_validate(job)
