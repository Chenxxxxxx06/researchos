"""Enumerations for the experiments context."""

from __future__ import annotations

from enum import StrEnum


class ExperimentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES: frozenset[ExperimentRunStatus] = frozenset(
    {
        ExperimentRunStatus.COMPLETED,
        ExperimentRunStatus.FAILED,
        ExperimentRunStatus.CANCELLED,
    }
)

# Legal run-status transitions. Terminal statuses accept nothing; a same-status
# update is treated as an idempotent no-op by the service (not a transition).
ALLOWED_TRANSITIONS: dict[ExperimentRunStatus, frozenset[ExperimentRunStatus]] = {
    ExperimentRunStatus.QUEUED: frozenset(
        {
            ExperimentRunStatus.RUNNING,
            ExperimentRunStatus.COMPLETED,
            ExperimentRunStatus.FAILED,
            ExperimentRunStatus.CANCELLED,
        }
    ),
    ExperimentRunStatus.RUNNING: frozenset(
        {
            ExperimentRunStatus.COMPLETED,
            ExperimentRunStatus.FAILED,
            ExperimentRunStatus.CANCELLED,
        }
    ),
    ExperimentRunStatus.COMPLETED: frozenset(),
    ExperimentRunStatus.FAILED: frozenset(),
    ExperimentRunStatus.CANCELLED: frozenset(),
}
