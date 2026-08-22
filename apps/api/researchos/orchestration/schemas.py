"""Typed API contracts for the durable orchestration control plane."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MissionTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    mission_step_id: uuid.UUID | None
    parent_task_id: uuid.UUID | None
    task_key: str
    title: str
    role: str
    agent_type: str | None
    status: str
    priority: int
    attempt: int
    max_attempts: int
    idempotency_key: str
    input_json: dict
    output_json: dict
    acceptance_json: list
    permissions_json: list
    budget_json: dict
    agent_run_id: uuid.UUID | None
    available_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    last_error_json: dict | None
    created_at: datetime
    updated_at: datetime


class TaskDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID
    required_artifact_schema: str | None


class TaskArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID
    schema_name: str
    schema_version: int
    content_hash: str
    uri: str | None
    metadata_json: dict
    producer_run_id: uuid.UUID | None
    visibility: str
    created_at: datetime


class ApprovalGateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID
    gate_kind: str
    status: str
    request_json: dict
    decision_json: dict
    requested_by: uuid.UUID
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    created_at: datetime


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    seq: int
    event_type: str
    payload_json: dict
    actor_id: uuid.UUID | None
    message: str | None
    created_at: datetime


class ActiveAgentStatus(BaseModel):
    task_id: uuid.UUID
    task_key: str
    title: str
    role: str
    agent_type: str | None
    status: str
    agent_run_id: uuid.UUID | None
    attempt: int
    started_at: datetime | None
    progress_percent: float
    current_action: str


class MissionProgressResponse(BaseModel):
    total_tasks: int
    completed_tasks: int
    running_tasks: int
    blocked_tasks: int
    failed_tasks: int
    progress_percent: float
    active_agents: list[ActiveAgentStatus]
    current_phase: str
    next_ready_tasks: list[str]
    blocker_messages: list[str]
    eta_seconds: int | None
    eta_basis: str


class OrchestrationGraphResponse(BaseModel):
    mission_id: uuid.UUID
    tasks: list[MissionTaskResponse]
    dependencies: list[TaskDependencyResponse]
    artifacts: list[TaskArtifactResponse]
    gates: list[ApprovalGateResponse]
    events: list[TaskEventResponse]
    counts: dict[str, int]
    progress: MissionProgressResponse


class AutopilotStartRequest(BaseModel):
    venue: str = Field(default="generic", min_length=1, max_length=80)
    auto_apply_code: bool = True
    isolated_workspace_confirmed: bool = False
    max_directions: int = Field(default=10, ge=1, le=10)
    pilot_first: bool = True
    allow_paid_compute: bool = False
    allow_trusted_local_execution: bool = False
    pilot_argv: list[str] = Field(
        default_factory=lambda: ["python", "-m", "compileall", "-q", "."],
        min_length=1,
        max_length=32,
    )
    full_argv: list[str] = Field(default_factory=list, max_length=32)
    run_cwd: str = Field(default=".", min_length=1, max_length=512)
    pilot_timeout_seconds: int = Field(default=180, ge=10, le=1800)
    full_timeout_seconds: int = Field(default=3600, ge=30, le=86_400)


class AutopilotStepResponse(BaseModel):
    graph: OrchestrationGraphResponse
    state: Literal["dispatched", "running", "blocked", "completed"]
    dispatched_task_id: uuid.UUID | None = None
    agent_run_id: uuid.UUID | None = None
    blockers: list[str] = Field(default_factory=list)
    next_action: str


class DispatchTaskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    context: dict = Field(default_factory=dict)


class DispatchTaskResponse(BaseModel):
    task_id: uuid.UUID
    agent_run_id: uuid.UUID
    status: str
    stream: str


class LeaseTaskRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=80)
    lease_seconds: int = Field(default=120, ge=30, le=1800)


class LeaseTaskResponse(BaseModel):
    task: MissionTaskResponse
    lease_token: uuid.UUID
    expires_at: datetime


class TaskLeaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    owner: str
    token: uuid.UUID
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime


class HeartbeatLeaseRequest(BaseModel):
    lease_seconds: int = Field(default=120, ge=30, le=1800)
    running: bool = True


class ArtifactSubmission(BaseModel):
    schema_name: str = Field(min_length=1, max_length=160)
    schema_version: int = Field(default=1, ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    uri: str | None = Field(default=None, max_length=2048)
    metadata: dict = Field(default_factory=dict)
    input_artifact_versions: list = Field(default_factory=list)
    visibility: Literal["private", "team", "published"] = "team"


class SubmitLeaseRequest(BaseModel):
    output: dict = Field(default_factory=dict)
    artifacts: list[ArtifactSubmission] = Field(default_factory=list, max_length=100)


class GateDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2000)


class CoordinatorTickResponse(BaseModel):
    graph: OrchestrationGraphResponse
    promoted: int
    reclaimed: int
    reconciled: int


class ResearchLoopCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    metric_name: str = Field(min_length=1, max_length=120)
    metric_direction: Literal["min", "max"]
    metric_aggregation: Literal["final", "best"] = "final"
    baseline_run_id: uuid.UUID
    fixed_budget_seconds: int = Field(default=300, ge=30, le=86_400)
    max_iterations: int = Field(default=12, ge=1, le=500)
    patience: int = Field(default=4, ge=1, le=100)
    min_delta: float = Field(default=0.0, ge=0)
    max_complexity_delta: int = Field(default=200, ge=-10_000, le=100_000)
    critic_threshold: float = Field(default=0.7, ge=0, le=1)
    editable_scopes: list[str] = Field(min_length=1, max_length=100)
    protected_scopes: list[str] = Field(default_factory=list, max_length=100)


class ResearchIterationCreateRequest(BaseModel):
    hypothesis: str = Field(min_length=1, max_length=5000)
    component: str = Field(min_length=1, max_length=120)
    expected_effect: str = Field(min_length=1, max_length=5000)
    changed_paths: list[str] = Field(min_length=1, max_length=100)
    agent_run_id: uuid.UUID | None = None


class ResearchIterationEvaluateRequest(BaseModel):
    experiment_run_id: uuid.UUID
    patch_id: uuid.UUID | None = None
    complexity_delta: int = Field(ge=-100_000, le=100_000)
    critic_score: float = Field(ge=0, le=1)
    rule_checks: dict[str, bool] = Field(min_length=1, max_length=100)


class ResearchLoopControlRequest(BaseModel):
    action: Literal["pause", "resume", "finalize", "cancel"]
    reason: str = Field(default="", max_length=2000)


class ResearchLoopIterationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    loop_id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID
    iteration_number: int
    status: str
    hypothesis: str
    component: str
    expected_effect: str
    changed_paths_json: list
    patch_id: uuid.UUID | None
    agent_run_id: uuid.UUID | None
    experiment_run_id: uuid.UUID | None
    code_commit_sha: str | None
    metric_value: float | None
    improvement: float | None
    complexity_delta: int | None
    critic_score: float | None
    rule_checks_json: dict
    decision_json: dict
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class ResearchLoopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID
    name: str
    status: str
    metric_name: str
    metric_direction: str
    metric_aggregation: str
    baseline_run_id: uuid.UUID
    best_run_id: uuid.UUID
    baseline_metric_value: float
    best_metric_value: float
    fixed_budget_seconds: int
    max_iterations: int
    patience: int
    min_delta: float
    max_complexity_delta: int
    critic_threshold: float
    current_iteration: int
    no_improvement_count: int
    editable_scope_json: list
    protected_scope_json: list
    stop_reason: str | None
    created_at: datetime
    updated_at: datetime
    iterations: list[ResearchLoopIterationResponse] = Field(default_factory=list)
