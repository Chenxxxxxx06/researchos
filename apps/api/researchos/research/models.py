"""Research ORM models: papers, sections, ideas, critiques, feed prefs."""

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

from .enums import IdeaStatus, PaperIngestStatus, PaperSectionKind


class Paper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A paper imported into a project's library. Always carries source metadata."""

    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint("project_id", "source", "external_id", name="uq_paper_project_source_ext"),
        Index("ix_papers_project_doi", "project_id", "doi"),
        Index("ix_papers_project_arxiv", "project_id", "arxiv_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingest_status: Mapped[PaperIngestStatus] = mapped_column(
        Enum(
            PaperIngestStatus,
            name="paper_ingest_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaperIngestStatus.PENDING,
    )
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    imported_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class PaperSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A typed full-text section parsed from a paper's HTML rendition."""

    __tablename__ = "paper_sections"
    __table_args__ = (UniqueConstraint("paper_id", "seq", name="uq_paper_section_seq"),)

    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    heading: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[PaperSectionKind] = mapped_column(
        Enum(
            PaperSectionKind,
            name="paper_section_kind",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaperSectionKind.OTHER,
    )


class ResearchFeedPref(TimestampMixin, Base):
    """Explicit followed-category overrides for a project's freshness feed."""

    __tablename__ = "research_feed_prefs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class Idea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ideas"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[IdeaStatus] = mapped_column(
        Enum(IdeaStatus, name="idea_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IdeaStatus.DRAFT,
    )
    novelty_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class ResearchCritique(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_critiques"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    novelty_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weaknesses_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_baselines_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    dataset_risks_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reproducibility_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Paper ids (library) that back this critique. No fabricated citations.
    citations_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
