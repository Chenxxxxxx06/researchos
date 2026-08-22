"""structured paper insights and tuple retrieval

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CARD_FIELDS = (
    "github_repositories_json",
    "paper_ideas_json",
    "benchmarks_json",
    "ablation_findings_json",
    "knowledge_tuples_json",
)


def upgrade() -> None:
    # PostgreSQL native enums do not learn new Python StrEnum members from ORM
    # metadata. Add every runtime role before any AgentRun can persist it.
    for value in (
        "idea_explorer",
        "benchmark",
        "leader",
        "viewer",
        "writer",
        "drawer",
        "progress",
    ):
        op.execute(f"ALTER TYPE agent_type ADD VALUE IF NOT EXISTS '{value}'")

    for field in _CARD_FIELDS:
        op.add_column(
            "reading_cards",
            sa.Column(
                field,
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    op.create_table(
        "paper_knowledge_tuples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reading_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tuple_index", sa.Integer(), nullable=False),
        sa.Column("tuple_kind", sa.String(32), nullable=False),
        sa.Column("head", sa.String(500), nullable=False),
        sa.Column("relation", sa.String(160), nullable=False),
        sa.Column("tail", sa.Text(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(head, '') || ' ' || "
                "coalesce(relation, '') || ' ' || coalesce(tail, '') || ' ' || "
                "coalesce(evidence_quote, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column(
            "embedding_model",
            sa.String(80),
            nullable=False,
            server_default="hashing-1024-v2",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reading_card_id"], ["reading_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["paper_sections.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reading_card_id", "tuple_index", name="uq_paper_tuple_card_index"),
    )
    op.create_index(
        "ix_paper_knowledge_tuples_project_id", "paper_knowledge_tuples", ["project_id"]
    )
    op.create_index(
        "ix_paper_knowledge_tuples_mission_id", "paper_knowledge_tuples", ["mission_id"]
    )
    op.create_index("ix_paper_knowledge_tuples_paper_id", "paper_knowledge_tuples", ["paper_id"])
    op.create_index(
        "ix_paper_knowledge_tuples_reading_card_id",
        "paper_knowledge_tuples",
        ["reading_card_id"],
    )
    op.create_index(
        "ix_paper_knowledge_tuples_section_id", "paper_knowledge_tuples", ["section_id"]
    )
    op.create_index(
        "ix_paper_tuples_project_mission",
        "paper_knowledge_tuples",
        ["project_id", "mission_id"],
    )
    op.create_index(
        "ix_paper_tuples_project_kind",
        "paper_knowledge_tuples",
        ["project_id", "tuple_kind"],
    )
    op.create_index(
        "ix_paper_tuples_search_tsv",
        "paper_knowledge_tuples",
        ["search_tsv"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_paper_tuples_embedding_hnsw",
        "paper_knowledge_tuples",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place. The added
    # values remain inert after the tables/columns from this revision are gone.
    op.drop_table("paper_knowledge_tuples")
    for field in reversed(_CARD_FIELDS):
        op.drop_column("reading_cards", field)
