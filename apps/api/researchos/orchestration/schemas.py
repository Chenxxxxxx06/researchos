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


class OrchestrationGraphResponse(BaseModel):
    mission_id: uuid.UUID
    tasks: list[MissionTaskResponse]
    dependencies: list[TaskDependencyResponse]
    artifacts: list[TaskArtifactResponse]
    gates: list[ApprovalGateResponse]
    events: list[TaskEventResponse]
    counts: dict[str, int]


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
