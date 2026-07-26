"""Coding chat DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from researchos.agents.enums import AgentRunStatus, AgentType


class CreateChatSessionRequest(BaseModel):
    title: str = Field(default="", max_length=200)


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    agent_type: AgentType
    created_at: datetime


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    role: Literal["user", "assistant"]
    content: str
    agent_run_id: uuid.UUID | None
    patch_id: uuid.UUID | None
    created_at: datetime


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse] = []


class CreateChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class CreateChatMessageResponse(BaseModel):
    message_id: uuid.UUID
    agent_run_id: uuid.UUID
    status: AgentRunStatus
    stream: str
