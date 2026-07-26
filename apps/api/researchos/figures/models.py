"""Figures ORM models: result anchors, figures, rendered assets."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from .enums import AnchorAggregation, FigureRenderStatus


class ResultAnchor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named binding from a LaTeX macro (``\\ROS<name>``) to a metric reduction."""

    __tablename__ = "result_anchors"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_result_anchors_project_name"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL = follow the experiment's latest COMPLETED run.
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True
    )
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregation: Mapped[AnchorAggregation] = mapped_column(
        Enum(
            AnchorAggregation,
            name="anchor_aggregation",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=AnchorAggregation.FINAL,
    )
    decimals: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    scale: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    suffix: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    captured_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class Figure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "figures"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_figures_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    spec_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[FigureRenderStatus] = mapped_column(
        Enum(
            FigureRenderStatus,
            name="figure_render_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=FigureRenderStatus.PENDING,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_style_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rendered_style_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_run_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_rendered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latex_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("latex_projects.id", ondelete="SET NULL"), nullable=True
    )
    usage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class FigureAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Latest rendered bytes per (figure, format); upserted, never accumulated."""

    __tablename__ = "figure_assets"
    __table_args__ = (
        UniqueConstraint("figure_id", "format", name="uq_figure_assets_figure_format"),
    )

    figure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("figures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
