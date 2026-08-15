"""rebuild paper chunk embeddings at 1024 dimensions

Existing chunks were embedded with the old 384-dim hashing profile and cannot
be converted, so they are deleted and rebuilt lazily by
``ensure_project_chunks`` under the active profile.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Old-profile vectors cannot survive a dimension change; drop them first.
    op.execute("DELETE FROM paper_chunks")
    op.drop_index("ix_paper_chunks_embedding_hnsw", table_name="paper_chunks")
    op.alter_column(
        "paper_chunks",
        "embedding",
        existing_type=Vector(384),
        type_=Vector(1024),
        existing_nullable=False,
    )
    op.alter_column(
        "paper_chunks",
        "embedding_model",
        existing_type=sa.String(80),
        server_default="hashing-1024-v2",
        existing_nullable=False,
    )
    op.create_index(
        "ix_paper_chunks_embedding_hnsw",
        "paper_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.execute("DELETE FROM paper_chunks")
    op.drop_index("ix_paper_chunks_embedding_hnsw", table_name="paper_chunks")
    op.alter_column(
        "paper_chunks",
        "embedding",
        existing_type=Vector(1024),
        type_=Vector(384),
        existing_nullable=False,
    )
    op.alter_column(
        "paper_chunks",
        "embedding_model",
        existing_type=sa.String(80),
        server_default="hashing-384-v1",
        existing_nullable=False,
    )
    op.create_index(
        "ix_paper_chunks_embedding_hnsw",
        "paper_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
