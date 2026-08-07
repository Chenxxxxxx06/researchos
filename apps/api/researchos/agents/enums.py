"""Enumerations for the agents context."""

from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    RESEARCH = "research"
    CRITIC = "critic"
    CODING = "coding"
    EXPERIMENT = "experiment"
    LATEX = "latex"
    READING_CARD = "reading_card"
    REVIEW_SECTION = "review_section"
    EXPERIMENT_PLANNER = "experiment_planner"
    SQL_ANALYST = "sql_analyst"
    CITATION_ORGANIZER = "citation_organizer"


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
