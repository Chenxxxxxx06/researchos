"""Patch proposal ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from .enums import PatchChangeType, PatchStatus


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class PatchProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patch_proposals"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[PatchStatus] = mapped_column(
        _enum(PatchStatus, "patch_status"), nullable=False, default=PatchStatus.PENDING
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    files: Mapped[list[PatchFile]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan", order_by="PatchFile.path"
    )


class PatchFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patch_files"

    patch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    change_type: Mapped[PatchChangeType] = mapped_column(
        _enum(PatchChangeType, "patch_change_type"), nullable=False
    )
    # Expected sha256 of the current file (None for create). Apply compares this
    # against the live file; a mismatch is a conflict.
    base_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    proposal: Mapped[PatchProposal] = relationship(back_populates="files")
    hunks: Mapped[list[PatchHunk]] = relationship(
        back_populates="file", cascade="all, delete-orphan", order_by="PatchHunk.new_start"
    )


class PatchHunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Display-only diff hunk (no partial apply in MVP)."""

    __tablename__ = "patch_hunks"

    patch_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    header: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    old_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    old_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    file: Mapped[PatchFile] = relationship(back_populates="hunks")
