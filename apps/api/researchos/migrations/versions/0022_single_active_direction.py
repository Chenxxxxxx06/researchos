"""enforce one approved research direction per project

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preserve the most recently updated active direction if an older database
    # already contains duplicates, then enforce the invariant at the DB layer.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY project_id ORDER BY updated_at DESC, id DESC
                   ) AS position
            FROM ideas
            WHERE status = 'active'
        )
        UPDATE ideas
        SET status = 'archived'
        FROM ranked
        WHERE ideas.id = ranked.id AND ranked.position > 1
        """
    )
    op.create_index(
        "uq_ideas_one_active_per_project",
        "ideas",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_ideas_one_active_per_project", table_name="ideas")
