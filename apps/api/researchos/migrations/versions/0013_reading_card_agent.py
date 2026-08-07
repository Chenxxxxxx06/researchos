"""add reading-card agent and immutable card versions

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'reading_card'")
    op.create_table(
        "reading_card_versions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["reading_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_id", "version", name="uq_reading_card_version"),
    )
    op.create_index("ix_reading_card_versions_project_id", "reading_card_versions", ["project_id"])
    op.create_index("ix_reading_card_versions_mission_id", "reading_card_versions", ["mission_id"])
    op.create_index("ix_reading_card_versions_paper_id", "reading_card_versions", ["paper_id"])
    op.create_index("ix_reading_card_versions_card_id", "reading_card_versions", ["card_id"])
    op.create_index(
        "ix_reading_card_versions_project_card",
        "reading_card_versions",
        ["project_id", "card_id"],
    )


def downgrade() -> None:
    op.drop_table("reading_card_versions")
    # PostgreSQL enum values cannot be removed safely in a generic downgrade.
