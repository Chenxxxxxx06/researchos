"""add review section agent type

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'review_section'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while rows may reference them.
    pass
