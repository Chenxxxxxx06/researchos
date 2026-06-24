"""LaTeX document ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from .enums import CompileStatus


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
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
