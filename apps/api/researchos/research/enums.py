"""Enumerations for the research context."""

from __future__ import annotations

from enum import StrEnum


class IdeaStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PaperIngestStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    ABSTRACT_ONLY = "abstract_only"
    FAILED = "failed"


class PaperSectionKind(StrEnum):
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    BACKGROUND = "background"
    METHOD = "method"
    EXPERIMENTS = "experiments"
    RESULTS = "results"
    RELATED_WORK = "related_work"
    CONCLUSION = "conclusion"
    APPENDIX = "appendix"
    OTHER = "other"
