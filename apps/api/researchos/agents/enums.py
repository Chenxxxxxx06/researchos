"""Enumerations for the agents context."""

from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    RESEARCH = "research"
    CRITIC = "critic"
    CODING = "coding"
    EXPERIMENT = "experiment"
    LATEX = "latex"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }


class ToolCallStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
