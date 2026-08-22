"""Persistent knowledge artifacts that connect papers to research missions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PaperChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Retrieval-sized paper text with full-text and pgvector indexes."""

    __tablename__ = "paper_chunks"
    __table_args__ = (
        UniqueConstraint("section_id", "chunk_index", name="uq_paper_chunk_section_index"),
        Index("ix_paper_chunks_project_paper", "project_id", "paper_id"),
        Index("ix_paper_chunks_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_paper_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    section_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    search_tsv: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(heading, '') || ' ' || content)",
            persisted=True,
        ),
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(80), nullable=False, default="hashing-1024-v2"
    )


class PaperKnowledgeTuple(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Evidence-linked semantic tuple extracted from a reviewed reading card.

    Tuples make ideas, benchmarks, ablations, results, and code links directly
    retrievable without flattening an entire reading card into one opaque blob.
    """

    __tablename__ = "paper_knowledge_tuples"
    __table_args__ = (
        UniqueConstraint("reading_card_id", "tuple_index", name="uq_paper_tuple_card_index"),
        Index("ix_paper_tuples_project_mission", "project_id", "mission_id"),
        Index("ix_paper_tuples_project_kind", "project_id", "tuple_kind"),
        Index("ix_paper_tuples_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_paper_tuples_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reading_card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tuple_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tuple_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    head: Mapped[str] = mapped_column(String(500), nullable=False)
    relation: Mapped[str] = mapped_column(String(160), nullable=False)
    tail: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_inference: Mapped[bool] = mapped_column(nullable=False, default=False)
    evidence_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="needs_evidence"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_tsv: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(head, '') || ' ' || "
            "coalesce(relation, '') || ' ' || coalesce(tail, '') || ' ' || "
            "coalesce(evidence_quote, ''))",
            persisted=True,
        ),
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(80), nullable=False, default="hashing-1024-v2"
    )


class MissionTopicCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_topic_clusters"
    __table_args__ = (
        UniqueConstraint("mission_id", "position", name="uq_mission_cluster_position"),
        Index("ix_mission_clusters_project_mission", "project_id", "mission_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keywords_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    algorithm: Mapped[str] = mapped_column(
        String(100), nullable=False, default="hashing-384-agglomerative-v1"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class MissionPaper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_papers"
    __table_args__ = (
        UniqueConstraint("mission_id", "paper_id", name="uq_mission_paper"),
        Index("ix_mission_papers_project_mission", "project_id", "mission_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mission_topic_clusters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    inclusion_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    included_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ReadingCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_cards"
    __table_args__ = (
        UniqueConstraint("mission_id", "paper_id", name="uq_reading_card_mission_paper"),
        Index("ix_reading_cards_project_mission", "project_id", "mission_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    research_question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reading_focus_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    method_flow_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    experimental_setup_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    key_results_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    conclusions_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    strengths_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    limitations_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reproducibility_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    github_repositories_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    paper_ideas_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    benchmarks_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ablation_findings_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    knowledge_tuples_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    claims_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReadingCardVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_card_versions"
    __table_args__ = (
        UniqueConstraint("card_id", "version", name="uq_reading_card_version"),
        Index("ix_reading_card_versions_project_card", "project_id", "card_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_cards.id", ondelete="CASCADE"), nullable=False, index=True
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


class ReadingNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_notes"
    __table_args__ = (Index("ix_reading_notes_project_paper", "project_id", "paper_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paper_sections.id", ondelete="SET NULL"), nullable=True
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
