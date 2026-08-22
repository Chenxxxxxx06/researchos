"""Release Studio API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReleaseKind = Literal["poster", "slides", "website"]


class CreateReleaseJobRequest(BaseModel):
    kind: ReleaseKind
    story_pack: str = Field(min_length=120, max_length=50_000)
    template: str | None = Field(default=None, max_length=80)


class ReleaseJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    engine: str
    model: str
    status: str
    external_run_id: str | None
    artifact_json: dict | None
    progress_json: dict
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ReleaseIntegrationStatus(BaseModel):
    available: bool
    service_url: str
    model: str = "qwen-plus"
    message: str
