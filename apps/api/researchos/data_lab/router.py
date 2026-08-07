"""Registered dataset and mission SQL Agent endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    CreateDatasetSourceRequest,
    DatasetSourceResponse,
    RunSqlQuestionRequest,
    SqlQueryResultResponse,
)
from .service import DataLabService

router = APIRouter(prefix="/projects/{project_id}", tags=["data-lab"])


@router.get("/datasets", response_model=list[DatasetSourceResponse])
async def list_datasets(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[DatasetSourceResponse]:
    items = await DataLabService(db).list_sources(user, project_id)
    return [DatasetSourceResponse.model_validate(item) for item in items]


@router.post(
    "/datasets",
    response_model=DatasetSourceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_dataset(
    project_id: uuid.UUID,
    payload: CreateDatasetSourceRequest,
    user: CurrentUser,
    db: DbSession,
) -> DatasetSourceResponse:
    return DatasetSourceResponse.model_validate(
        await DataLabService(db).create_source(user, project_id, payload)
    )


@router.post(
    "/missions/{mission_id}/sql-query",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def run_sql_question(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: RunSqlQuestionRequest,
    user: CurrentUser,
    db: DbSession,
) -> CreateAgentRunResponse:
    await DataLabService(db).validate_question(
        user, project_id, mission_id, payload.dataset_source_id
    )
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.SQL_ANALYST,
        message=payload.question,
        context={
            "mission_id": str(mission_id),
            "dataset_source_id": str(payload.dataset_source_id),
            "question": payload.question,
        },
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id,
        status=run.status,
        stream=f"/ws?project_id={project_id}",
    )


@router.get("/missions/{mission_id}/sql-results", response_model=list[SqlQueryResultResponse])
async def list_sql_results(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[SqlQueryResultResponse]:
    items = await DataLabService(db).list_results(user, project_id, mission_id)
    return [SqlQueryResultResponse.model_validate(item) for item in items]
