"""Unified management-center response."""

from __future__ import annotations

from pydantic import BaseModel


class ManagementSummaryResponse(BaseModel):
    organization: dict
    project: dict
    researchers: list[dict]
    papers: list[dict]
    experiment_plans: list[dict]
    reading_notes: list[dict]
    counts: dict[str, int]
