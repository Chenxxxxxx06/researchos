"""ide workspace: patch proposals + coding agent type

Adds patch_proposals, patch_files, patch_hunks and the patch_status /
patch_change_type enums, and extends agent_type with 'coding'.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(col: str) -> sa.Column:
    return sa.Column(col, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    # Extend the existing agent_type enum. ADD VALUE is supported inside a
    # transaction on PG12+ as long as the value is not used in the same tx.
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'coding'")

    patch_status = postgresql.ENUM(
        "pending", "applied", "rejected", "conflict", name="patch_status"
    )
    patch_change_type = postgresql.ENUM("create", "modify", "delete", name="patch_change_type")

    op.create_table(
        "patch_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", patch_status, nullable=False, server_default="pending"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_patch_proposals_project_id", "patch_proposals", ["project_id"])
    op.create_index("ix_patch_proposals_agent_run_id", "patch_proposals", ["agent_run_id"])
    op.create_index("ix_patch_proposals_created_by", "patch_proposals", ["created_by"])
    op.create_index(
        "ix_patch_proposals_project_created", "patch_proposals", ["project_id", "created_at"]
    )

    op.create_table(
        "patch_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("change_type", patch_change_type, nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=True),
        sa.Column("new_content", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["patch_id"], ["patch_proposals.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_patch_files_patch_id", "patch_files", ["patch_id"])

    op.create_table(
        "patch_hunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patch_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("header", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("old_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("old_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["patch_file_id"], ["patch_files.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_patch_hunks_patch_file_id", "patch_hunks", ["patch_file_id"])


def downgrade() -> None:
    op.drop_table("patch_hunks")
    op.drop_table("patch_files")
    op.drop_table("patch_proposals")

    bind = op.get_bind()
    postgresql.ENUM(name="patch_change_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="patch_status").drop(bind, checkfirst=True)
    # NOTE: 'coding' is intentionally NOT removed from agent_type — PostgreSQL
    # does not support removing enum values without recreating the type.
