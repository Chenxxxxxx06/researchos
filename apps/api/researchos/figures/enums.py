"""Enumerations for the figures context."""

from __future__ import annotations

from enum import StrEnum


class AnchorAggregation(StrEnum):
    FINAL = "final"
    BEST = "best"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"


class FigureRenderStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    RENDERED = "rendered"
    FAILED = "failed"
