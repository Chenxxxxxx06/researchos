"""Enumerations for the skills context."""

from __future__ import annotations

from enum import StrEnum


class SkillVisibility(StrEnum):
    FIRST_PARTY = "first_party"
    CUSTOM = "custom"


class SkillModule(StrEnum):
    RESEARCH = "research"
    IDE = "ide"
    EXPERIMENTS = "experiments"
    PAPER = "paper"
