"""Research Mission workflow enumerations."""

from __future__ import annotations

from enum import StrEnum


class MissionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MissionStepKind(StrEnum):
    SCOPE = "scope"
    LITERATURE = "literature"
    READING = "reading"
    REVIEW = "review"
    EXPERIMENT_PLAN = "experiment_plan"


class MissionStepStatus(StrEnum):
    LOCKED = "locked"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"


MISSION_STEP_ORDER: tuple[MissionStepKind, ...] = (
    MissionStepKind.SCOPE,
    MissionStepKind.LITERATURE,
    MissionStepKind.READING,
    MissionStepKind.REVIEW,
    MissionStepKind.EXPERIMENT_PLAN,
)
