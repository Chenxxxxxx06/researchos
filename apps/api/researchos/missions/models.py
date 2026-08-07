"""Persistent Research Mission workflow models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from .enums import MissionStatus, MissionStepKind, MissionStepStatus


def _enum(enum_cls, name: str):
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class ResearchMission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A durable topic-to-review-to-experiment-plan workflow."""

    __tablename__ = "research_missions"
    __table_args__ = (
        Index("ix_research_missions_project_activity", "project_id", "last_activity_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[MissionStatus] = mapped_column(
        _enum(MissionStatus, "mission_status"), nullable=False, default=MissionStatus.DRAFT
    )
    current_step: Mapped[MissionStepKind] = mapped_column(
        _enum(MissionStepKind, "mission_step_kind"),
        nullable=False,
        default=MissionStepKind.SCOPE,
    )
    scope_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class MissionStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One reviewable, versioned step in a Research Mission."""

    __tablename__ = "mission_steps"
    __table_args__ = (
        UniqueConstraint("mission_id", "step_kind", name="uq_mission_step_kind"),
        Index("ix_mission_steps_project_mission", "project_id", "mission_id"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_kind: Mapped[MissionStepKind] = mapped_column(
        _enum(MissionStepKind, "mission_step_kind"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[MissionStepStatus] = mapped_column(
        _enum(MissionStepStatus, "mission_step_status"), nullable=False
    )
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MissionEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human-readable business timeline with structured audit details."""

    __tablename__ = "mission_events"
    __table_args__ = (
        Index("ix_mission_events_mission_created", "mission_id", "created_at"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    step_kind: Mapped[MissionStepKind | None] = mapped_column(
        _enum(MissionStepKind, "mission_step_kind"), nullable=True
    )
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
