"""Experiment DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import ExperimentRunStatus


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    goal: str | None = Field(default=None, max_length=10_000)


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    goal: str | None
    created_at: datetime


class CreateRunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    status: ExperimentRunStatus = ExperimentRunStatus.RUNNING
    git_commit: str | None = None
    command: str | None = None
    config: dict = Field(default_factory=dict)


class UpdateRunRequest(BaseModel):
    status: ExperimentRunStatus | None = None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: ExperimentRunStatus
    git_commit: str | None
    command: str | None
    config_json: dict
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class MetricPoint(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    step: int = 0
    value: float


class RecordMetricsRequest(BaseModel):
    points: list[MetricPoint] = Field(min_length=1, max_length=5000)


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    step: int
    value: float


class AppendLogRequest(BaseModel):
    level: str = "info"
    message: str = Field(min_length=1, max_length=20_000)


class LogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    level: str
    message: str
    created_at: datetime


class CreateArtifactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    artifact_type: str = "file"
    uri: str = ""
    size_bytes: int | None = None
    metadata: dict = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    artifact_type: str
    uri: str
    size_bytes: int | None
    created_at: datetime
