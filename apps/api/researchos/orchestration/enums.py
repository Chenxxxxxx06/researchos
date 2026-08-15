"""Durable orchestration states and role identifiers."""

from __future__ import annotations

from enum import StrEnum


class MissionTaskStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    LEASED = "leased"
    RUNNING = "running"
    ARTIFACT_READY = "artifact_ready"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    RETRYABLE_FAILED = "retryable_failed"
    TERMINAL_FAILED = "terminal_failed"
    CANCELLED = "cancelled"


class ApprovalGateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactVisibility(StrEnum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLISHED = "published"
