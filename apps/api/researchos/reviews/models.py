"""Structured review outline, sections, and version snapshots."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_documents"
    __table_args__ = (UniqueConstraint("mission_id", name="uq_review_document_mission"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="outline")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ReviewSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_sections"
    __table_args__ = (
        UniqueConstraint("review_id", "section_key", name="uq_review_section_key"),
        Index("ix_review_sections_mission_position", "mission_id", "position"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_key: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    citations_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    claims_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="outline")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ReviewVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_versions"
    __table_args__ = (
        UniqueConstraint("review_id", "version", name="uq_review_version"),
        Index("ix_review_versions_project_review", "project_id", "review_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_documents.id", ondelete="CASCADE"), nullable=False, index=True
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
