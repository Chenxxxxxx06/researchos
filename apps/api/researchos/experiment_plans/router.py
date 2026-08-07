"""Mission experiment-plan endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    ExperimentPlanResponse,
    ExperimentPlanVersionResponse,
    GenerateExperimentPlanRequest,
    PublishExperimentPlanResponse,
    UpsertExperimentPlanRequest,
)
from .service import ExperimentPlanService

router = APIRouter(
    prefix="/projects/{project_id}/missions/{mission_id}/experiment-plan",
    tags=["mission-experiment-plan"],
)


@router.get("", response_model=ExperimentPlanResponse)
async def get_plan(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ExperimentPlanResponse:
    return ExperimentPlanResponse.model_validate(
        await ExperimentPlanService(db).get(user, project_id, mission_id)
    )


@router.put("", response_model=ExperimentPlanResponse, dependencies=[Depends(require_csrf)])
async def upsert_plan(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: UpsertExperimentPlanRequest,
    user: CurrentUser,
    db: DbSession,
) -> ExperimentPlanResponse:
    return ExperimentPlanResponse.model_validate(
        await ExperimentPlanService(db).upsert(user, project_id, mission_id, payload)
    )


@router.post(
    "/generate",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def generate_plan(
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: GenerateExperimentPlanRequest,
    user: CurrentUser,
    db: DbSession,
) -> CreateAgentRunResponse:
    await ExperimentPlanService(db).validate_generation(user, project_id, mission_id, payload)
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.EXPERIMENT_PLANNER,
        message="Design a falsifiable, evidence-bound experiment plan from the mission review.",
        context={
            "mission_id": str(mission_id),
            "expected_version": payload.expected_version,
        },
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id,
        status=run.status,
        stream=f"/ws?project_id={project_id}",
    )


@router.get("/versions", response_model=list[ExperimentPlanVersionResponse])
async def list_versions(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ExperimentPlanVersionResponse]:
    versions = await ExperimentPlanService(db).versions(user, project_id, mission_id)
    return [ExperimentPlanVersionResponse.model_validate(item) for item in versions]


@router.post(
    "/publish",
    response_model=PublishExperimentPlanResponse,
    dependencies=[Depends(require_csrf)],
)
async def publish_plan(
    project_id: uuid.UUID, mission_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> PublishExperimentPlanResponse:
    plan, experiment = await ExperimentPlanService(db).publish(user, project_id, mission_id)
    return PublishExperimentPlanResponse(
        plan=ExperimentPlanResponse.model_validate(plan), experiment_id=experiment.id
    )
