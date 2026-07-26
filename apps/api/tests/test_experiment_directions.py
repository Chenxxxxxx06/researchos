"""Pure tests for metric direction resolution, dedup, and series reduction."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from researchos.experiments.directions import dedupe_points, metric_direction, reduce_series
from researchos.figures.enums import AnchorAggregation


def _row(step: int, value: float, *, created_at: datetime | None = None, rid: str | None = None):
    return SimpleNamespace(
        step=step,
        value=value,
        created_at=created_at,
        id=rid or str(uuid.uuid4()),
    )


# --- metric_direction --------------------------------------------------------


def test_explicit_metadata_wins_over_heuristic() -> None:
    # "accuracy" would be max by heuristic; explicit metadata forces min.
    meta = {"accuracy": {"direction": "min"}}
    assert metric_direction("accuracy", meta) == "min"
    # And the reverse: a loss-like name explicitly marked max.
    assert metric_direction("val_loss", {"val_loss": {"direction": "max"}}) == "max"


@pytest.mark.parametrize("name", ["perplexity", "wer", "rmse", "val_loss", "cer", "latency_ms"])
def test_min_hints(name: str) -> None:
    assert metric_direction(name, None) == "min"


@pytest.mark.parametrize("name", ["accuracy", "val_acc", "f1", "bleu"])
def test_default_is_max(name: str) -> None:
    assert metric_direction(name, None) == "max"


def test_metadata_for_other_metric_does_not_apply() -> None:
    meta = {"other": {"direction": "min"}}
    assert metric_direction("accuracy", meta) == "max"


def test_malformed_metadata_falls_back_to_heuristic() -> None:
    assert metric_direction("loss", {"loss": {"direction": "sideways"}}) == "min"
    assert metric_direction("loss", {"loss": "min"}) == "min"  # not a mapping entry


# --- dedupe_points -----------------------------------------------------------


def test_dedupe_keeps_latest_duplicate_step() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 1, 2, tzinfo=UTC)
    rows = [
        _row(0, 1.0, created_at=t0),
        _row(1, 0.8, created_at=t0),
        _row(1, 0.5, created_at=t1),  # later write for step 1 wins
    ]
    assert dedupe_points(rows) == [(0, 1.0), (1, 0.5)]


def test_dedupe_ties_break_on_id_and_sorts_by_step() -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        _row(2, 5.0, created_at=t, rid="b"),
        _row(2, 7.0, created_at=t, rid="a"),  # same created_at, lower id loses
        _row(0, 1.0, created_at=t, rid="c"),
    ]
    assert dedupe_points(rows) == [(0, 1.0), (2, 5.0)]


def test_dedupe_handles_missing_created_at() -> None:
    rows = [
        _row(0, 1.0, created_at=None),
        _row(0, 2.0, created_at=datetime(2026, 1, 1, tzinfo=UTC)),
    ]
    assert dedupe_points(rows) == [(0, 2.0)]


# --- reduce_series -----------------------------------------------------------

POINTS = [(0, 3.0), (1, 1.0), (2, 2.0)]


def test_reduce_final_is_value_at_max_step() -> None:
    assert reduce_series(POINTS, aggregation=AnchorAggregation.FINAL, direction="max") == 2.0


def test_reduce_best_respects_direction() -> None:
    assert reduce_series(POINTS, aggregation=AnchorAggregation.BEST, direction="max") == 3.0
    assert reduce_series(POINTS, aggregation=AnchorAggregation.BEST, direction="min") == 1.0


def test_reduce_min_max_mean_literal() -> None:
    assert reduce_series(POINTS, aggregation=AnchorAggregation.MIN, direction="max") == 1.0
    assert reduce_series(POINTS, aggregation=AnchorAggregation.MAX, direction="min") == 3.0
    assert reduce_series(POINTS, aggregation=AnchorAggregation.MEAN, direction="max") == 2.0


def test_reduce_empty_series_returns_none() -> None:
    for aggregation in AnchorAggregation:
        assert reduce_series([], aggregation=aggregation, direction="max") is None
