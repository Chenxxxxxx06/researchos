"""add pgvector paper chunks and clustering metadata

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "paper_chunks",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("section_seq", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(500), nullable=False, server_default=""),
        sa.Column("section_kind", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(heading, '') || ' ' || content)",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "embedding_model", sa.String(80), nullable=False, server_default="hashing-384-v1"
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["paper_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "chunk_index", name="uq_paper_chunk_section_index"),
    )
    op.create_index("ix_paper_chunks_project_id", "paper_chunks", ["project_id"])
    op.create_index("ix_paper_chunks_paper_id", "paper_chunks", ["paper_id"])
    op.create_index("ix_paper_chunks_section_id", "paper_chunks", ["section_id"])
    op.create_index("ix_paper_chunks_project_paper", "paper_chunks", ["project_id", "paper_id"])
    op.create_index(
        "ix_paper_chunks_search_tsv", "paper_chunks", ["search_tsv"], postgresql_using="gin"
    )
    op.create_index(
        "ix_paper_chunks_embedding_hnsw",
        "paper_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.add_column(
        "mission_topic_clusters",
        sa.Column(
            "algorithm",
            sa.String(100),
            nullable=False,
            server_default="hashing-384-agglomerative-v1",
        ),
    )
    op.add_column(
        "mission_topic_clusters",
        sa.Column("status", sa.String(32), nullable=False, server_default="generated"),
    )


def downgrade() -> None:
    op.drop_column("mission_topic_clusters", "status")
    op.drop_column("mission_topic_clusters", "algorithm")
    op.drop_table("paper_chunks")
