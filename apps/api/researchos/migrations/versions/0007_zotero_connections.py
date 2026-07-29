"""add project-scoped Zotero connections

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "zotero_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("library_type", sa.String(16), nullable=False, server_default="user"),
        sa.Column("library_id", sa.String(64), nullable=False),
        sa.Column("api_key", sa.String(512), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "include_collections_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("last_library_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("project_id", name="uq_zotero_connection_project"),
    )
    op.create_index(
        "ix_zotero_connections_project_id",
        "zotero_connections",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_zotero_connections_project_id", table_name="zotero_connections")
    op.drop_table("zotero_connections")
