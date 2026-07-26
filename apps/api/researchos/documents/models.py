"""LaTeX document ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
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

from .enums import CompileStatus, SuggestionOp, SuggestionStatus


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class LatexProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "latex_projects"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    main_file_path: Mapped[str] = mapped_column(String(255), nullable=False, default="main.tex")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class DocumentFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_files"
    __table_args__ = (
        UniqueConstraint("latex_project_id", "path", name="uq_document_file_project_path"),
    )

    latex_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("latex_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DocumentFileRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable content snapshot per file version (CAS merge base + history)."""

    __tablename__ = "document_file_revisions"
    __table_args__ = (
        UniqueConstraint("document_file_id", "version", name="uq_document_revision_file_version"),
    )

    document_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DocumentSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tracked-change suggestion (old->new spans) awaiting user review."""

    __tablename__ = "document_suggestions"
    __table_args__ = (
        Index("ix_document_suggestions_project_status", "latex_project_id", "status"),
    )

    latex_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("latex_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    op: Mapped[SuggestionOp] = mapped_column(
        _enum(SuggestionOp, "document_suggestion_op"), nullable=False
    )
    status: Mapped[SuggestionStatus] = mapped_column(
        _enum(SuggestionStatus, "document_suggestion_status"),
        nullable=False,
        default=SuggestionStatus.PROPOSED,
    )
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'range' (offsets trusted at base_version) or 'text' (re-anchor by search).
    anchor_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="range")
    # {start, end, anchor_prefix, anchor_suffix, offset_start, offset_end}
    range_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    old_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    new_text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    spans_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(String(50), nullable=True)
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LatexCompileJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "latex_compile_jobs"

    latex_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("latex_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[CompileStatus] = mapped_column(
        Enum(CompileStatus, name="compile_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CompileStatus.QUEUED,
    )
    engine: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structural preview model + diagnostics from the pure-Python parse (D7).
    preview_model_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diagnostics_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
