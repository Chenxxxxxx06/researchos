"""add mission citation organizer agent and audits

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'citation_organizer'")
    op.create_table(
        "mission_citation_audits",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("items_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("duplicate_groups_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("missing_field_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bibtex_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id"),
    )
    for column in ("project_id", "mission_id", "agent_run_id", "created_by"):
        op.create_index(f"ix_mission_citation_audits_{column}", "mission_citation_audits", [column])


def downgrade() -> None:
    op.drop_table("mission_citation_audits")
