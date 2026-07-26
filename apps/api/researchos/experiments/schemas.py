"""Experiment DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .enums import ExperimentRunStatus

MAX_METRIC_META_KEYS = 200


class MetricMetaEntry(BaseModel):
    direction: Literal["min", "max"]
    unit: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, max_length=120)


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    goal: str | None = Field(default=None, max_length=10_000)


class UpdateExperimentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    goal: str | None = Field(default=None, max_length=10_000)
    metric_meta: dict[str, MetricMetaEntry] | None = None

    @field_validator("metric_meta")
    @classmethod
    def _cap_keys(
        cls, value: dict[str, MetricMetaEntry] | None
    ) -> dict[str, MetricMetaEntry] | None:
        if value is not None and len(value) > MAX_METRIC_META_KEYS:
            raise ValueError(f"metric_meta accepts at most {MAX_METRIC_META_KEYS} metrics")
        return value


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    goal: str | None
    metric_meta: dict = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metric_meta", "metric_meta_json"),
    )
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


# --- ingest tokens -----------------------------------------------------------


class CreateIngestTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class IngestTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class IngestTokenCreatedResponse(IngestTokenResponse):
    # Plaintext token; present only in the creation response.
    token: str


# --- NDJSON ingest lines -----------------------------------------------------


class MetricLine(BaseModel):
    t: Literal["metric"]
    name: str = Field(min_length=1, max_length=120)
    step: int = 0
    value: float


class LogLine(BaseModel):
    t: Literal["log"]
    level: str = Field(default="info", max_length=20)
    msg: str = Field(min_length=1, max_length=20_000)


class StatusLine(BaseModel):
    t: Literal["status"]
    status: ExperimentRunStatus


IngestLine = Annotated[MetricLine | LogLine | StatusLine, Field(discriminator="t")]


class RejectedLine(BaseModel):
    line: int
    error: str


class IngestResult(BaseModel):
    accepted: int
    rejected: list[RejectedLine]
    run_status: ExperimentRunStatus
