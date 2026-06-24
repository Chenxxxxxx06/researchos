"""WebSocket event envelope, aligned with packages/shared-schemas/src/events.ts.

The envelope shape and the event-type vocabulary must match the frontend
contract. A contract test asserts the agent event types stay in sync.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ResourceType = Literal[
    "agent_run",
    "experiment_run",
    "latex_compile",
    "runtime_command",
    "skill_installation",
    "project",
]

# Phase 2 agent event types (subset of shared-schemas EVENT_TYPES).
AGENT_EVENT_TYPES: tuple[str, ...] = (
    "agent.run.started",
    "agent.run.token",
    "agent.run.tool_call.started",
    "agent.run.tool_call.completed",
    "agent.run.completed",
    "agent.run.failed",
    "agent.run.cancelled",
)


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    event_type: str
    project_id: str
    resource_type: ResourceType
    resource_id: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


def build_agent_event(
    *,
    event_type: str,
    project_id: uuid.UUID | str,
    agent_run_id: uuid.UUID | str,
    payload: dict[str, Any],
    timestamp: datetime | None = None,
) -> dict:
    ts = (timestamp or datetime.now(tz=UTC)).isoformat()
    return EventEnvelope(
        event_type=event_type,
        project_id=str(project_id),
        resource_type="agent_run",
        resource_id=str(agent_run_id),
        timestamp=ts,
        payload=payload,
    ).model_dump()
