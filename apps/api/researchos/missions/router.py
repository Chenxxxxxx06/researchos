"""Research Mission endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .enums import MissionStatus, MissionStepKind
from .schemas import (
    ApproveMissionStepRequest,
    CreateMissionRequest,
    MissionDetailResponse,
    MissionEventResponse,
    MissionStepResponse,
    MissionSummaryResponse,
    UpdateMissionRequest,
    UpdateMissionStepRequest,
)
from .service import MissionService

router = APIRouter(prefix="/projects/{project_id}/missions", tags=["research-missions"])


def _detail(mission, steps) -> MissionDetailResponse:
    return MissionDetailResponse(
        **MissionSummaryResponse.model_validate(mission).model_dump(),
        steps=[MissionStepResponse.model_validate(step) for step in steps],
    )


@router.get("", response_model=Page[MissionSummaryResponse])
async def list_missions(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    mission_status: MissionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[MissionSummaryResponse]:
    items, total = await MissionService(db).list_missions(
        user,
        project_id,
        status=mission_status,
        limit=limit,
        offset=offset,
    )
    return Page[MissionSummaryResponse](
        items=[MissionSummaryResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=MissionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_mission(
    project_id: uuid.UUID,
    payload: CreateMissionRequest,
    user: CurrentUser,
    db: DbSession,
) -> MissionDetailResponse:
    mission, steps = await MissionService(db).create(user, project_id, payload)
    return _detail(mission, steps)


@router.get("/{mission_id}", response_model=MissionDetailResponse)
async def get_mission(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> MissionDetailResponse:
    mission, steps = await MissionService(db).get(user, project_id, mission_id)
    return _detail(mission, steps)


@router.patch(
    "/{mission_id}",
    response_model=MissionDetailResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_mission(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: UpdateMissionRequest,
    user: CurrentUser,
    db: DbSession,
) -> MissionDetailResponse:
    mission, steps = await MissionService(db).update(
        user, project_id, mission_id, payload
    )
    return _detail(mission, steps)


@router.put(
    "/{mission_id}/steps/{step_kind}",
    response_model=MissionDetailResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_mission_step(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    step_kind: MissionStepKind,
    payload: UpdateMissionStepRequest,
    user: CurrentUser,
    db: DbSession,
) -> MissionDetailResponse:
    mission, steps = await MissionService(db).update_step(
        user, project_id, mission_id, step_kind, payload
    )
    return _detail(mission, steps)


@router.post(
    "/{mission_id}/steps/{step_kind}/approve",
    response_model=MissionDetailResponse,
    dependencies=[Depends(require_csrf)],
)
async def approve_mission_step(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    step_kind: MissionStepKind,
    payload: ApproveMissionStepRequest,
    user: CurrentUser,
    db: DbSession,
) -> MissionDetailResponse:
    mission, steps = await MissionService(db).approve_step(
        user,
        project_id,
        mission_id,
        step_kind,
        expected_version=payload.expected_version,
        note=payload.note,
    )
    return _detail(mission, steps)


@router.get("/{mission_id}/timeline", response_model=Page[MissionEventResponse])
async def get_mission_timeline(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[MissionEventResponse]:
    items, total = await MissionService(db).timeline(
        user, project_id, mission_id, limit=limit, offset=offset
    )
    return Page[MissionEventResponse](
        items=[MissionEventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
