"""Agents DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import AgentRunStatus, AgentType, ToolCallStatus


class AgentRunContext(BaseModel):
    idea_id: uuid.UUID | None = None
    mission_id: uuid.UUID | None = None
    mission_task_id: uuid.UUID | None = None
    llm_config_id: uuid.UUID | None = None
    venue: str | None = Field(default=None, max_length=80)
    section: str | None = Field(default=None, max_length=80)
    auto_apply_patch: bool = False
    isolated_workspace_confirmed: bool = False
    # "Explain this section" seeds the research agent with a library paper and
    # optional section indices; both flow verbatim into input_json.context.
    paper_id: uuid.UUID | None = None
    section_seqs: list[int] | None = Field(default=None, max_length=64)
    section_kinds: list[str] | None = Field(default=None, max_length=16)
    # Optional per-run narrowing. Slugs still have to be installed and enabled.
    skill_slugs: list[str] | None = Field(default=None, max_length=8)


class CreateAgentRunRequest(BaseModel):
    agent_type: AgentType
    message: str = Field(min_length=1, max_length=10_000)
    context: AgentRunContext = Field(default_factory=AgentRunContext)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    agent_type: AgentType
    status: AgentRunStatus
    input_json: dict
    output_json: dict | None
    error_json: dict | None
    token_usage_json: dict
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CreateAgentRunResponse(BaseModel):
    agent_run_id: uuid.UUID
    status: AgentRunStatus
    stream: str


class ToolCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    tool_name: str
    arguments_json: dict
    result_json: dict | None
    status: ToolCallStatus
    error: str | None


class AgentCapabilityResponse(BaseModel):
    agent_type: AgentType
    role: str
    purpose: str
    input_contract: list[str]
    output_contract: str
    tools: list[str]
    autonomy: str
    approval_boundaries: list[str]
    status: str = "available"
    operational_blockers: list[str] = Field(default_factory=list)


class AgentRunEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    event_type: str
    payload_json: dict
    created_at: datetime
