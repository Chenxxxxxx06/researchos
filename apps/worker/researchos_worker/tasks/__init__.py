"""Celery task modules.

Re-exported so ``import researchos_worker.tasks`` registers every task with the
app (Celery's ``include=`` list imports the same modules; this keeps direct
imports and test discovery in sync with it).
"""

from . import agents, figures, health, ingestion

__all__ = ["agents", "figures", "health", "ingestion"]
