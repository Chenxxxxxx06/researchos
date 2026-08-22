"""Persistent release-generation jobs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReleaseGenerationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "release_generation_jobs"
    __table_args__ = (
        Index("ix_release_jobs_project_created", "project_id", "created_at"),
        Index("ix_release_jobs_project_status", "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    engine: Mapped[str] = mapped_column(String(40), nullable=False, default="autodesign")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="qwen-plus")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    story_pack: Mapped[str] = mapped_column(Text, nullable=False)
    external_run_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    artifact_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    progress_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
