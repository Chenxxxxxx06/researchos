"""Research Inbox DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InboxSourceType = Literal["message", "note", "file", "audio_transcript"]
InboxAnalysisMode = Literal["direction", "meeting_summary", "audio_to_paper"]


class CreateInboxItemRequest(BaseModel):
    source_type: InboxSourceType
    sender: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    content_text: str = Field(min_length=1, max_length=100_000)
    original_filename: str | None = Field(default=None, max_length=500)
    media_type: str | None = Field(default=None, max_length=200)


class InboxItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_type: InboxSourceType
    sender: str | None
    title: str
    content_text: str
    original_filename: str | None
    media_type: str | None
    agent_run_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AnalyzeInboxItemResponse(BaseModel):
    item_id: uuid.UUID
    agent_run_id: uuid.UUID
    status: str


class AnalyzeInboxItemRequest(BaseModel):
    mode: InboxAnalysisMode = "direction"
