"""add configurable reading focus and structured findings

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in (
        "reading_focus_json",
        "experimental_setup_json",
        "key_results_json",
        "conclusions_json",
    ):
        op.add_column(
            "reading_cards",
            sa.Column(
                name,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    for name in (
        "conclusions_json",
        "key_results_json",
        "experimental_setup_json",
        "reading_focus_json",
    ):
        op.drop_column("reading_cards", name)
