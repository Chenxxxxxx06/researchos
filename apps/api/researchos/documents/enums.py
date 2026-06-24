"""Enumerations for the documents (LaTeX) context."""

from __future__ import annotations

from enum import StrEnum


class CompileStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
