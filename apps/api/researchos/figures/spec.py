"""FigureSpec pydantic models (stored as ``figures.spec_json``).

The pydantic layer enforces structural caps (series count, inline points,
smoothing window, label lengths). Tenancy of referenced runs/experiments is
validated by the service at create/update/render time.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

MAX_SERIES = 8
MAX_INLINE_POINTS = 2000
MAX_SMOOTHING_WINDOW = 500


class RunMetricSource(BaseModel):
    kind: Literal["run_metric"]
    # Either a pinned run or an experiment (latest COMPLETED run).
    run_id: uuid.UUID | None = None
    experiment_id: uuid.UUID | None = None
    metric_name: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def _require_reference(self) -> RunMetricSource:
        if self.run_id is None and self.experiment_id is None:
            raise ValueError("run_metric source requires run_id or experiment_id")
        return self


class InlineSource(BaseModel):
    kind: Literal["inline"]
    points: list[tuple[float, float]] = Field(min_length=1, max_length=MAX_INLINE_POINTS)


SeriesSource = Annotated[RunMetricSource | InlineSource, Field(discriminator="kind")]


class FigureSeries(BaseModel):
    source: SeriesSource
    label: str | None = Field(default=None, max_length=120)
    smoothing_window: int = Field(default=1, ge=1, le=MAX_SMOOTHING_WINDOW)


class FigureSpecModel(BaseModel):
    chart: Literal["line", "bar", "scatter"]
    series: list[FigureSeries] = Field(min_length=1, max_length=MAX_SERIES)
    title: str | None = Field(default=None, max_length=200)
    x_label: str | None = Field(default=None, max_length=200)
    y_label: str | None = Field(default=None, max_length=200)
    legend: bool = True
    y_scale: Literal["linear", "log"] = "linear"
    # None = resolve from the creator's preferences at render time.
    style_slug: str | None = Field(default=None, max_length=64)
