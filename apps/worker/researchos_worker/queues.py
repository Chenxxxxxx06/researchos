"""Queue names and task routing.

Phase 0 runs all queues in a single worker process. The routing table is
defined now so that production can split queues across dedicated worker
deployments without code changes — only the ``--queues`` flag differs.
"""

from __future__ import annotations

from enum import StrEnum


class Queue(StrEnum):
    AGENTS = "agents"
    INGESTION = "ingestion"
    RUNTIME = "runtime"
    LATEX = "latex"
    EXPERIMENTS = "experiments"
    SKILLS = "skills"
    DEFAULT = "default"


ALL_QUEUES: tuple[str, ...] = tuple(q.value for q in Queue)

# Map task-name prefixes to queues. Health tasks run on the default queue.
TASK_ROUTES: dict[str, dict[str, str]] = {
    "agents.*": {"queue": Queue.AGENTS},
    "ingestion.*": {"queue": Queue.INGESTION},
    "runtime.*": {"queue": Queue.RUNTIME},
    "latex.*": {"queue": Queue.LATEX},
    "experiments.*": {"queue": Queue.EXPERIMENTS},
    "skills.*": {"queue": Queue.SKILLS},
}
