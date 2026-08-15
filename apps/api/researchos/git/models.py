"""Immutable provenance records for approved external repository imports."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RepositorySnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repository_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "destination_path", name="uq_repository_snapshot_destination"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    approved_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_owner: Mapped[str] = mapped_column(String(100), nullable=False)
    source_repo: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="importing")
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_spdx: Mapped[str | None] = mapped_column(String(80), nullable=True)
    license_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    skipped_files_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    submodules_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coding_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    coding_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
