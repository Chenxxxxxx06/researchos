"""Pure metric-series helpers: direction resolution, dedup, and reduction.

Single source of truth for every consumer that reduces a metric series
(anchors, figures, the experiment agent summary). No DB or network access —
inputs are plain rows/points, outputs are plain values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from statistics import fmean
from typing import TYPE_CHECKING, Any, Literal

from researchos.figures.enums import AnchorAggregation

if TYPE_CHECKING:
    from .models import ExperimentMetric

Direction = Literal["min", "max"]

# Substring hints for lower-is-better metrics. Explicit metadata always wins.
_MIN_HINTS = (
    "loss",
    "error",
    "err_",
    "_err",
    "perplexity",
    "ppl",
    "wer",
    "cer",
    "mae",
    "mse",
    "rmse",
    "regret",
    "latency",
)


def metric_direction(name: str, metric_meta: Mapping[str, Any] | None) -> Direction:
    """Explicit metadata wins; else expanded substring heuristic; else 'max'."""

    if metric_meta:
        entry = metric_meta.get(name)
        if isinstance(entry, Mapping):
            declared = entry.get("direction")
            if declared in ("min", "max"):
                return declared
    lowered = name.lower()
    if any(hint in lowered for hint in _MIN_HINTS):
        return "min"
    return "max"


def _recency_key(row: ExperimentMetric | Any) -> tuple[int, datetime, str]:
    """Order rows by (created_at, id); rows without created_at sort earliest."""

    created = getattr(row, "created_at", None)
    if created is None:
        return (0, datetime.min, str(getattr(row, "id", "")))
    return (1, created, str(getattr(row, "id", "")))


def dedupe_points(rows: Sequence[ExperimentMetric | Any]) -> list[tuple[int, float]]:
    """Collapse duplicate (name-scoped) steps keeping the latest row.

    Latest = max ``created_at``, then max ``id``. Returns step-sorted
    ``(step, value)`` pairs.
    """

    winners: dict[int, Any] = {}
    for row in rows:
        step = int(row.step)
        current = winners.get(step)
        if current is None or _recency_key(row) >= _recency_key(current):
            winners[step] = row
    return [(step, float(winners[step].value)) for step in sorted(winners)]


def reduce_series(
    points: Sequence[tuple[int, float]],
    *,
    aggregation: AnchorAggregation,
    direction: Direction,
) -> float | None:
    """Reduce a step-sorted series to a single value; ``None`` for empty series.

    ``final`` = value at max step; ``best`` = min/max per direction;
    ``min``/``max``/``mean`` are literal.
    """

    if not points:
        return None
    values = [value for _, value in points]
    if aggregation is AnchorAggregation.FINAL:
        return max(points, key=lambda p: p[0])[1]
    if aggregation is AnchorAggregation.BEST:
        return min(values) if direction == "min" else max(values)
    if aggregation is AnchorAggregation.MIN:
        return min(values)
    if aggregation is AnchorAggregation.MAX:
        return max(values)
    return fmean(values)
