"""Structured experiment plans and immutable snapshots."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExperimentPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_plans"
    __table_args__ = (UniqueConstraint("mission_id", name="uq_experiment_plan_mission"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    research_gap: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    variables_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    baselines_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    datasets_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metrics_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    matrix_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    decision_rules_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    stop_conditions_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risks_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reproducibility_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    published_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ExperimentPlanVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_experiment_plan_version"),
        Index("ix_experiment_plan_versions_project_plan", "project_id", "plan_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
