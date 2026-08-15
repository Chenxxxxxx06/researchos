"""approved repository snapshots and durable SSH audit references

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ssh_executions_profile_id_fkey", "ssh_executions", type_="foreignkey")
    op.create_foreign_key(
        "ssh_executions_profile_id_fkey",
        "ssh_executions",
        "ssh_profiles",
        ["profile_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "repository_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("source_owner", sa.String(100), nullable=False),
        sa.Column("source_repo", sa.String(100), nullable=False),
        sa.Column("destination_path", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="importing"),
        sa.Column("commit_sha", sa.String(64)),
        sa.Column("default_branch", sa.String(255)),
        sa.Column("license_spdx", sa.String(80)),
        sa.Column("license_path", sa.String(1024)),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "skipped_files_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "submodules_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("manifest_hash", sa.String(64)),
        sa.Column("workspace_commit_sha", sa.String(64)),
        sa.Column("coding_session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("coding_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["idea_id"], ["ideas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["coding_session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["coding_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "project_id", "destination_path", name="uq_repository_snapshot_destination"
        ),
    )
    op.create_index("ix_repository_snapshots_project_id", "repository_snapshots", ["project_id"])
    op.create_index("ix_repository_snapshots_idea_id", "repository_snapshots", ["idea_id"])
    op.create_index("ix_repository_snapshots_approved_by", "repository_snapshots", ["approved_by"])
    op.create_index(
        "ix_repository_snapshots_coding_session_id",
        "repository_snapshots",
        ["coding_session_id"],
    )
    op.create_index(
        "ix_repository_snapshots_coding_run_id", "repository_snapshots", ["coding_run_id"]
    )


def downgrade() -> None:
    op.drop_table("repository_snapshots")
    op.drop_constraint("ssh_executions_profile_id_fkey", "ssh_executions", type_="foreignkey")
    op.create_foreign_key(
        "ssh_executions_profile_id_fkey",
        "ssh_executions",
        "ssh_profiles",
        ["profile_id"],
        ["id"],
        ondelete="CASCADE",
    )
