"""Enumerations for the experiments context."""

from __future__ import annotations

from enum import StrEnum


class ExperimentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
