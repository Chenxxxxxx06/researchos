"""Agent run endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from researchos.common.deps import CurrentUser, DbSession, require_csrf
from researchos.common.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page

from .schemas import (
    AgentRunEventResponse,
    AgentRunResponse,
    CreateAgentRunRequest,
    CreateAgentRunResponse,
)
from .service import AgentRunService

router = APIRouter(prefix="/projects/{project_id}/agents", tags=["agents"])


@router.post(
    "/runs",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_run(
    project_id: uuid.UUID,
    payload: CreateAgentRunRequest,
    user: CurrentUser,
    db: DbSession,
) -> CreateAgentRunResponse:
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=payload.agent_type,
        message=payload.message,
        context=payload.context.model_dump(mode="json", exclude_none=True),
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id, status=run.status, stream=f"/ws?project_id={project_id}"
    )


@router.get("/runs", response_model=Page[AgentRunResponse])
async def list_runs(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> Page[AgentRunResponse]:
    page = await AgentRunService(db).list_runs(user, project_id, limit=limit, offset=offset)
    return Page[AgentRunResponse](
        items=[AgentRunResponse.model_validate(r) for r in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_run(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> AgentRunResponse:
    run = await AgentRunService(db).get_run(user, project_id, run_id)
    return AgentRunResponse.model_validate(run)


@router.get("/runs/{run_id}/events", response_model=list[AgentRunEventResponse])
async def get_run_events(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    after_seq: int = Query(default=-1, ge=-1),
) -> list[AgentRunEventResponse]:
    events = await AgentRunService(db).get_events(user, project_id, run_id, after_seq=after_seq)
    return [AgentRunEventResponse.model_validate(e) for e in events]


@router.post(
    "/runs/{run_id}/cancel",
    response_model=AgentRunResponse,
    dependencies=[Depends(require_csrf)],
)
async def cancel_run(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> AgentRunResponse:
    run = await AgentRunService(db).cancel_run(user, project_id, run_id)
    return AgentRunResponse.model_validate(run)
