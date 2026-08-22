"""agent role enum values and tuple trust labels

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AGENT_TYPES = (
    "idea_explorer",
    "benchmark",
    "leader",
    "viewer",
    "writer",
    "drawer",
    "progress",
)


def upgrade() -> None:
    for value in _AGENT_TYPES:
        op.execute(f"ALTER TYPE agent_type ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column(
        "paper_knowledge_tuples",
        sa.Column("is_inference", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "paper_knowledge_tuples",
        sa.Column(
            "evidence_status",
            sa.String(32),
            nullable=False,
            server_default="needs_evidence",
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_knowledge_tuples", "evidence_status")
    op.drop_column("paper_knowledge_tuples", "is_inference")
    # PostgreSQL enum values remain inert because in-place removal is unsafe.
