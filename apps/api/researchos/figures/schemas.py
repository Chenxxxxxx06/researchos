"""Anchor / figure / staleness / preset DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .enums import AnchorAggregation, FigureRenderStatus
from .macros import macro_name
from .models import Figure, ResultAnchor
from .presets import StylePreset
from .spec import FigureSpecModel

# LaTeX control words are letters-only.
ANCHOR_NAME_PATTERN = r"^[A-Za-z]{1,48}$"


class CreateAnchorRequest(BaseModel):
    name: str = Field(pattern=ANCHOR_NAME_PATTERN)
    experiment_id: uuid.UUID
    run_id: uuid.UUID | None = None
    metric_name: str = Field(min_length=1, max_length=120)
    aggregation: AnchorAggregation = AnchorAggregation.FINAL
    decimals: int = Field(default=2, ge=0, le=10)
    scale: float = 1.0
    suffix: str = Field(default="", max_length=16)


class UpdateAnchorRequest(BaseModel):
    name: str | None = Field(default=None, pattern=ANCHOR_NAME_PATTERN)
    experiment_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    metric_name: str | None = Field(default=None, min_length=1, max_length=120)
    aggregation: AnchorAggregation | None = None
    decimals: int | None = Field(default=None, ge=0, le=10)
    scale: float | None = None
    suffix: str | None = Field(default=None, max_length=16)


class AnchorResponse(BaseModel):
    id: uuid.UUID
    name: str
    macro: str
    experiment_id: uuid.UUID
    run_id: uuid.UUID | None
    metric_name: str
    aggregation: AnchorAggregation
    decimals: int
    scale: float
    suffix: str
    captured_value: float | None
    captured_run_id: uuid.UUID | None
    captured_at: datetime | None
    stale: bool
    created_at: datetime

    @classmethod
    def from_model(cls, anchor: ResultAnchor) -> AnchorResponse:
        return cls(
            id=anchor.id,
            name=anchor.name,
            macro=f"\\{macro_name(anchor.name)}",
            experiment_id=anchor.experiment_id,
            run_id=anchor.run_id,
            metric_name=anchor.metric_name,
            aggregation=anchor.aggregation,
            decimals=anchor.decimals,
            scale=anchor.scale,
            suffix=anchor.suffix,
            captured_value=anchor.captured_value,
            captured_run_id=anchor.captured_run_id,
            captured_at=anchor.captured_at,
            stale=anchor.stale,
            created_at=anchor.created_at,
        )


class RefreshedAnchorItem(BaseModel):
    id: uuid.UUID
    name: str
    value: float | None
    formatted: str
    run_id: uuid.UUID | None
    resolved: bool


class RefreshAnchorsResponse(BaseModel):
    refreshed: int
    unresolved: int
    anchors: list[RefreshedAnchorItem]


class AnchorStalenessItem(BaseModel):
    anchor_id: uuid.UUID
    name: str
    stale: bool
    captured_run_id: uuid.UUID | None
    captured_value: float | None
    latest_run_id: uuid.UUID | None
    latest_value: float | None
    delta: float | None
    delta_pct: float | None


class AnchorStalenessResponse(BaseModel):
    stale_count: int
    items: list[AnchorStalenessItem]


class CreateFigureRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    spec: FigureSpecModel


class UpdateFigureRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    spec: FigureSpecModel | None = None
    latex_project_id: uuid.UUID | None = None
    usage_path: str | None = Field(default=None, max_length=512)


class FigureResponse(BaseModel):
    id: uuid.UUID
    name: str
    spec: dict
    status: FigureRenderStatus
    stale: bool
    style_outdated: bool
    last_error: str | None
    rendered_style_slug: str | None
    rendered_style_version: str | None
    source_run_ids: list[str]
    last_rendered_at: datetime | None
    latex_project_id: uuid.UUID | None
    usage_path: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, figure: Figure, *, style_outdated: bool) -> FigureResponse:
        return cls(
            id=figure.id,
            name=figure.name,
            spec=figure.spec_json,
            status=figure.status,
            stale=figure.stale,
            style_outdated=style_outdated,
            last_error=figure.last_error,
            rendered_style_slug=figure.rendered_style_slug,
            rendered_style_version=figure.rendered_style_version,
            source_run_ids=[str(rid) for rid in (figure.source_run_ids or [])],
            last_rendered_at=figure.last_rendered_at,
            latex_project_id=figure.latex_project_id,
            usage_path=figure.usage_path,
            created_at=figure.created_at,
        )


class RenderFigureRequest(BaseModel):
    mode: Literal["sync", "async"] = "async"


class RenderedAssetInfo(BaseModel):
    format: str
    size_bytes: int
    sha256: str


class RenderFigureResponse(BaseModel):
    figure_id: uuid.UUID
    status: FigureRenderStatus
    assets: list[RenderedAssetInfo] = Field(default_factory=list)


class PresetStyleInfo(BaseModel):
    """Drives frontend SVG thumbnails (CONSOLIDATION §5)."""

    palette: list[str]
    font_family: Literal["serif", "sans"]
    grid: bool
    legend_frame: bool


class StylePresetResponse(BaseModel):
    slug: str
    version: str
    name: str
    description: str
    palette: list[str]
    style: PresetStyleInfo

    @classmethod
    def from_preset(cls, preset: StylePreset) -> StylePresetResponse:
        return cls(
            slug=preset.slug,
            version=preset.version,
            name=preset.name,
            description=preset.description,
            palette=list(preset.palette),
            style=PresetStyleInfo(
                palette=list(preset.palette),
                font_family=preset.font_family,
                grid=preset.grid,
                legend_frame=preset.legend_frame,
            ),
        )
