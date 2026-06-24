"""Patch proposal endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .schemas import ApplyResultResponse, CreatePatchRequest, PatchResponse
from .service import PatchService

router = APIRouter(prefix="/projects/{project_id}/workspace/patches", tags=["patches"])


@router.post(
    "",
    response_model=PatchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_patch(
    project_id: uuid.UUID, payload: CreatePatchRequest, user: CurrentUser, db: DbSession
) -> PatchResponse:
    proposal = await PatchService(db).create_patch(
        user, project_id, summary=payload.summary, files=payload.files
    )
    return PatchResponse.model_validate(proposal)


@router.get("", response_model=Page[PatchResponse])
async def list_patches(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[PatchResponse]:
    page = await PatchService(db).list_patches(user, project_id, limit=limit, offset=offset)
    return Page[PatchResponse](
        items=[PatchResponse.model_validate(p) for p in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{patch_id}", response_model=PatchResponse)
async def get_patch(
    project_id: uuid.UUID, patch_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> PatchResponse:
    proposal = await PatchService(db).get_patch(user, project_id, patch_id)
    return PatchResponse.model_validate(proposal)


@router.post(
    "/{patch_id}/apply",
    response_model=ApplyResultResponse,
    dependencies=[Depends(require_csrf)],
)
async def apply_patch(
    project_id: uuid.UUID, patch_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ApplyResultResponse:
    return await PatchService(db).apply_patch(user, project_id, patch_id)


@router.post(
    "/{patch_id}/reject",
    response_model=PatchResponse,
    dependencies=[Depends(require_csrf)],
)
async def reject_patch(
    project_id: uuid.UUID, patch_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> PatchResponse:
    proposal = await PatchService(db).reject_patch(user, project_id, patch_id)
    return PatchResponse.model_validate(proposal)
