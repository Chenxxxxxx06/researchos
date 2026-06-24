"""per-project llm provider configurations

Adds llm_provider_configs so each project can have its own LLM endpoint,
model, and key, managed from the Settings UI.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(col: str) -> sa.Column:
    return sa.Column(col, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "llm_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default="default"),
        sa.Column(
            "provider_type", sa.String(30), nullable=False, server_default="openai_compatible"
        ),
        sa.Column(
            "base_url", sa.String(1024), nullable=False, server_default="https://api.openai.com/v1"
        ),
        sa.Column("model", sa.String(120), nullable=False, server_default="gpt-4o"),
        sa.Column("api_key", sa.String(512), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_llm_provider_configs_project_id", "llm_provider_configs", ["project_id"])


def downgrade() -> None:
    op.drop_table("llm_provider_configs")
