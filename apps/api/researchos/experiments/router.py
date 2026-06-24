"""Experiment endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from researchos.agents.enums import AgentType
from researchos.agents.schemas import CreateAgentRunResponse
from researchos.agents.service import AgentRunService
from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .schemas import (
    AppendLogRequest,
    ArtifactResponse,
    CreateArtifactRequest,
    CreateExperimentRequest,
    CreateRunRequest,
    ExperimentResponse,
    LogResponse,
    MetricResponse,
    RecordMetricsRequest,
    RunResponse,
    UpdateRunRequest,
)
from .service import ExperimentService

router = APIRouter(prefix="/projects/{project_id}", tags=["experiments"])


@router.get("/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ExperimentResponse]:
    items = await ExperimentService(db).list_experiments(user, project_id)
    return [ExperimentResponse.model_validate(e) for e in items]


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_experiment(
    project_id: uuid.UUID, payload: CreateExperimentRequest, user: CurrentUser, db: DbSession
) -> ExperimentResponse:
    exp = await ExperimentService(db).create_experiment(
        user, project_id, name=payload.name, description=payload.description, goal=payload.goal
    )
    return ExperimentResponse.model_validate(exp)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    project_id: uuid.UUID, experiment_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ExperimentResponse:
    exp = await ExperimentService(db).get_experiment(user, project_id, experiment_id)
    return ExperimentResponse.model_validate(exp)


@router.get("/experiments/{experiment_id}/runs", response_model=list[RunResponse])
async def list_runs(
    project_id: uuid.UUID, experiment_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[RunResponse]:
    runs = await ExperimentService(db).list_runs(user, project_id, experiment_id)
    return [RunResponse.model_validate(r) for r in runs]


@router.post(
    "/experiments/{experiment_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_run(
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    payload: CreateRunRequest,
    user: CurrentUser,
    db: DbSession,
) -> RunResponse:
    run = await ExperimentService(db).create_run(user, project_id, experiment_id, payload)
    return RunResponse.model_validate(run)


@router.get("/experiment-runs", response_model=list[RunResponse])
async def list_project_runs(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[RunResponse]:
    runs = await ExperimentService(db).list_project_runs(user, project_id)
    return [RunResponse.model_validate(r) for r in runs]


@router.get("/experiment-runs/{run_id}", response_model=RunResponse)
async def get_run(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> RunResponse:
    run = await ExperimentService(db).get_run(user, project_id, run_id)
    return RunResponse.model_validate(run)


@router.patch(
    "/experiment-runs/{run_id}", response_model=RunResponse, dependencies=[Depends(require_csrf)]
)
async def update_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: UpdateRunRequest,
    user: CurrentUser,
    db: DbSession,
) -> RunResponse:
    svc = ExperimentService(db)
    run = await svc.get_run(user, project_id, run_id)
    if payload.status is not None:
        run = await svc.update_run_status(user, project_id, run_id, payload.status)
    return RunResponse.model_validate(run)


@router.get("/experiment-runs/{run_id}/metrics", response_model=list[MetricResponse])
async def list_metrics(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[MetricResponse]:
    metrics = await ExperimentService(db).list_metrics(user, project_id, run_id)
    return [MetricResponse.model_validate(m) for m in metrics]


@router.post(
    "/experiment-runs/{run_id}/metrics",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def record_metrics(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: RecordMetricsRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    count = await ExperimentService(db).record_metrics(user, project_id, run_id, payload.points)
    return {"recorded": count}


@router.get("/experiment-runs/{run_id}/logs", response_model=list[LogResponse])
async def list_logs(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[LogResponse]:
    logs = await ExperimentService(db).list_logs(user, project_id, run_id)
    return [LogResponse.model_validate(log) for log in logs]


@router.post(
    "/experiment-runs/{run_id}/logs",
    response_model=LogResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def append_log(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: AppendLogRequest,
    user: CurrentUser,
    db: DbSession,
) -> LogResponse:
    log = await ExperimentService(db).append_log(
        user, project_id, run_id, level=payload.level, message=payload.message
    )
    return LogResponse.model_validate(log)


@router.get("/experiment-runs/{run_id}/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ArtifactResponse]:
    artifacts = await ExperimentService(db).list_artifacts(user, project_id, run_id)
    return [ArtifactResponse.model_validate(a) for a in artifacts]


@router.post(
    "/experiment-runs/{run_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_artifact(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: CreateArtifactRequest,
    user: CurrentUser,
    db: DbSession,
) -> ArtifactResponse:
    artifact = await ExperimentService(db).create_artifact(user, project_id, run_id, payload)
    return ArtifactResponse.model_validate(artifact)


@router.post(
    "/experiment-runs/{run_id}/analyze",
    response_model=CreateAgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def analyze_run(
    project_id: uuid.UUID, run_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> CreateAgentRunResponse:
    # Ensure access + existence, then launch an experiment-analysis agent run.
    await ExperimentService(db).get_run(user, project_id, run_id)
    run = await AgentRunService(db).create_run(
        user,
        project_id,
        agent_type=AgentType.EXPERIMENT,
        message="Analyze experiment run.",
        context={"experiment_run_id": str(run_id)},
    )
    return CreateAgentRunResponse(
        agent_run_id=run.id, status=run.status, stream=f"/ws?project_id={project_id}"
    )
