"""release jobs and real LaTeX PDF artifacts

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("latex_compile_jobs", sa.Column("pdf_path", sa.String(1024), nullable=True))
    op.add_column("latex_compile_jobs", sa.Column("pdf_size", sa.Integer(), nullable=True))
    op.add_column(
        "latex_compile_jobs", sa.Column("source_fingerprint", sa.String(64), nullable=True)
    )
    op.add_column("latex_compile_jobs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.create_index(
        "ix_latex_compile_jobs_source_fingerprint",
        "latex_compile_jobs",
        ["latex_project_id", "source_fingerprint"],
    )

    op.create_table(
        "release_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("engine", sa.String(40), nullable=False, server_default="autodesign"),
        sa.Column("model", sa.String(120), nullable=False, server_default="qwen-plus"),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("story_pack", sa.Text(), nullable=False),
        sa.Column("external_run_id", sa.String(160), nullable=True),
        sa.Column("artifact_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "progress_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_release_generation_jobs_project_id",
        "release_generation_jobs",
        ["project_id"],
    )
    op.create_index(
        "ix_release_generation_jobs_created_by",
        "release_generation_jobs",
        ["created_by"],
    )
    op.create_index(
        "ix_release_generation_jobs_external_run_id",
        "release_generation_jobs",
        ["external_run_id"],
    )
    op.create_index(
        "ix_release_jobs_project_created",
        "release_generation_jobs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_release_jobs_project_status",
        "release_generation_jobs",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("release_generation_jobs")
    op.drop_index("ix_latex_compile_jobs_source_fingerprint", table_name="latex_compile_jobs")
    op.drop_column("latex_compile_jobs", "duration_ms")
    op.drop_column("latex_compile_jobs", "source_fingerprint")
    op.drop_column("latex_compile_jobs", "pdf_size")
    op.drop_column("latex_compile_jobs", "pdf_path")
