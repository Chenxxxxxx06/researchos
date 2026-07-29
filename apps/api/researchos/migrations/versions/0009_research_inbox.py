"""add research inbox items

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_inbox_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("sender", sa.String(200), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("media_type", sa.String(200), nullable=True),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_research_inbox_items_project_id",
        "research_inbox_items",
        ["project_id"],
    )
    op.create_index(
        "ix_research_inbox_items_agent_run_id",
        "research_inbox_items",
        ["agent_run_id"],
    )
    op.create_index(
        "ix_research_inbox_items_created_by",
        "research_inbox_items",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_inbox_items_created_by",
        table_name="research_inbox_items",
    )
    op.drop_index(
        "ix_research_inbox_items_agent_run_id",
        table_name="research_inbox_items",
    )
    op.drop_index(
        "ix_research_inbox_items_project_id",
        table_name="research_inbox_items",
    )
    op.drop_table("research_inbox_items")
