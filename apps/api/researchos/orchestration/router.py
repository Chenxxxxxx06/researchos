"""Durable mission DAG and worker lease endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    CoordinatorTickResponse,
    DispatchTaskRequest,
    DispatchTaskResponse,
    GateDecisionRequest,
    HeartbeatLeaseRequest,
    LeaseTaskRequest,
    LeaseTaskResponse,
    MissionTaskResponse,
    OrchestrationGraphResponse,
    SubmitLeaseRequest,
    TaskLeaseResponse,
)
from .service import OrchestrationService

router = APIRouter(prefix="/projects/{project_id}/orchestration", tags=["orchestration"])


@router.get("/missions/{mission_id}", response_model=OrchestrationGraphResponse)
async def get_graph(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> OrchestrationGraphResponse:
    return await OrchestrationService(db).graph(user, project_id, mission_id)


@router.post(
    "/missions/{mission_id}/bootstrap",
    response_model=OrchestrationGraphResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def bootstrap_graph(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> OrchestrationGraphResponse:
    return await OrchestrationService(db).bootstrap(user, project_id, mission_id)


@router.post(
    "/missions/{mission_id}/tick",
    response_model=CoordinatorTickResponse,
    dependencies=[Depends(require_csrf)],
)
async def coordinator_tick(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> CoordinatorTickResponse:
    return await OrchestrationService(db).tick(user, project_id, mission_id)


@router.post(
    "/tasks/{task_id}/dispatch",
    response_model=DispatchTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def dispatch_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: DispatchTaskRequest,
    user: CurrentUser,
    db: DbSession,
) -> DispatchTaskResponse:
    return await OrchestrationService(db).dispatch(
        user,
        project_id,
        task_id,
        message=payload.message,
        context=payload.context,
    )


@router.post(
    "/leases/next",
    response_model=LeaseTaskResponse,
    dependencies=[Depends(require_csrf)],
)
async def lease_next_task(
    project_id: uuid.UUID,
    payload: LeaseTaskRequest,
    user: CurrentUser,
    db: DbSession,
) -> LeaseTaskResponse:
    return await OrchestrationService(db).lease_next(
        user,
        project_id,
        owner=payload.owner,
        role=payload.role,
        lease_seconds=payload.lease_seconds,
    )


@router.post(
    "/leases/{token}/heartbeat",
    response_model=TaskLeaseResponse,
    dependencies=[Depends(require_csrf)],
)
async def heartbeat_task_lease(
    project_id: uuid.UUID,
    token: uuid.UUID,
    payload: HeartbeatLeaseRequest,
    user: CurrentUser,
    db: DbSession,
) -> TaskLeaseResponse:
    lease = await OrchestrationService(db).heartbeat(
        user,
        project_id,
        token,
        lease_seconds=payload.lease_seconds,
        running=payload.running,
    )
    return TaskLeaseResponse.model_validate(lease)


@router.post(
    "/leases/{token}/submit",
    response_model=MissionTaskResponse,
    dependencies=[Depends(require_csrf)],
)
async def submit_task_lease(
    project_id: uuid.UUID,
    token: uuid.UUID,
    payload: SubmitLeaseRequest,
    user: CurrentUser,
    db: DbSession,
) -> MissionTaskResponse:
    task = await OrchestrationService(db).submit_lease(
        user,
        project_id,
        token,
        output=payload.output,
        artifacts=payload.artifacts,
    )
    return MissionTaskResponse.model_validate(task)


@router.post(
    "/gates/{gate_id}/decision",
    response_model=MissionTaskResponse,
    dependencies=[Depends(require_csrf)],
)
async def decide_approval_gate(
    project_id: uuid.UUID,
    gate_id: uuid.UUID,
    payload: GateDecisionRequest,
    user: CurrentUser,
    db: DbSession,
) -> MissionTaskResponse:
    task = await OrchestrationService(db).decide_gate(
        user,
        project_id,
        gate_id,
        approve=payload.decision == "approve",
        note=payload.note,
    )
    return MissionTaskResponse.model_validate(task)
