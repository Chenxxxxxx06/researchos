"""Research Mission API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import MissionStatus, MissionStepKind, MissionStepStatus


class CreateMissionRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    objective: str = Field(default="", max_length=20_000)
    field: str | None = Field(default=None, max_length=120)
    scope: dict = Field(default_factory=dict)

    @field_validator("topic", "objective", "field")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class UpdateMissionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    topic: str | None = Field(default=None, min_length=2, max_length=300)
    objective: str | None = Field(default=None, max_length=20_000)
    field: str | None = Field(default=None, max_length=120)
    scope: dict | None = None
    status: MissionStatus | None = None

    @field_validator("topic", "objective", "field")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class UpdateMissionStepRequest(BaseModel):
    expected_version: int = Field(ge=1)
    input: dict | None = None
    output: dict | None = None
    status: MissionStepStatus | None = None


class ApproveMissionStepRequest(BaseModel):
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=2_000)


class MissionStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    project_id: uuid.UUID
    step_kind: MissionStepKind
    position: int
    status: MissionStepStatus
    input_json: dict
    output_json: dict
    version: int
    started_at: datetime | None
    completed_at: datetime | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class MissionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    topic: str
    objective: str
    field: str | None
    status: MissionStatus
    current_step: MissionStepKind
    scope_json: dict
    progress: float
    version: int
    last_activity_at: datetime
    created_by: uuid.UUID
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MissionDetailResponse(MissionSummaryResponse):
    steps: list[MissionStepResponse]


class MissionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    project_id: uuid.UUID
    event_type: str
    summary: str
    step_kind: MissionStepKind | None
    payload_json: dict
    actor_id: uuid.UUID | None
    created_at: datetime
