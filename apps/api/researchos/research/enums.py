"""Enumerations for the research context."""

from __future__ import annotations

from enum import StrEnum


class IdeaStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
