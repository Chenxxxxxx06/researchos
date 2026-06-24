"""experiments, latex documents, and skills

Adds the Experiment Dashboard, Paper (LaTeX) Workspace, and Skills Marketplace
schemas, and extends agent_type with 'experiment' and 'latex'.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(col: str) -> sa.Column:
    return sa.Column(col, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _uuid(col: str, *, nullable: bool = False, pk: bool = False) -> sa.Column:
    return sa.Column(col, postgresql.UUID(as_uuid=True), primary_key=pk, nullable=nullable)


def upgrade() -> None:
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'experiment'")
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'latex'")

    run_status = postgresql.ENUM(
        "queued", "running", "completed", "failed", "cancelled", name="experiment_run_status"
    )
    compile_status = postgresql.ENUM(
        "queued", "running", "succeeded", "failed", name="compile_status"
    )
    skill_visibility = postgresql.ENUM("first_party", "custom", name="skill_visibility")

    # --- experiments -------------------------------------------------------
    op.create_table(
        "experiments",
        _uuid("id", pk=True),
        _uuid("project_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("default_config_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        _uuid("created_by"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_experiments_project_id", "experiments", ["project_id"])

    op.create_table(
        "experiment_runs",
        _uuid("id", pk=True),
        _uuid("experiment_id"),
        _uuid("project_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", run_status, nullable=False, server_default="queued"),
        sa.Column("git_commit", sa.String(64), nullable=True),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("config_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("created_by"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_experiment_runs_experiment_id", "experiment_runs", ["experiment_id"])
    op.create_index("ix_experiment_runs_project_id", "experiment_runs", ["project_id"])

    op.create_table(
        "experiment_metrics",
        _uuid("id", pk=True),
        _uuid("run_id"),
        _uuid("project_id"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("value", sa.Float(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_experiment_metrics_run_id", "experiment_metrics", ["run_id"])
    op.create_index(
        "ix_experiment_metrics_run_name_step", "experiment_metrics", ["run_id", "name", "step"]
    )

    op.create_table(
        "experiment_logs",
        _uuid("id", pk=True),
        _uuid("run_id"),
        _uuid("project_id"),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_experiment_logs_run_id", "experiment_logs", ["run_id"])

    op.create_table(
        "experiment_artifacts",
        _uuid("id", pk=True),
        _uuid("run_id"),
        _uuid("project_id"),
        sa.Column("artifact_type", sa.String(50), nullable=False, server_default="file"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("uri", sa.String(1024), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_experiment_artifacts_run_id", "experiment_artifacts", ["run_id"])

    # --- latex documents ---------------------------------------------------
    op.create_table(
        "latex_projects",
        _uuid("id", pk=True),
        _uuid("project_id"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("main_file_path", sa.String(255), nullable=False, server_default="main.tex"),
        _uuid("created_by"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_latex_projects_project_id", "latex_projects", ["project_id"])

    op.create_table(
        "document_files",
        _uuid("id", pk=True),
        _uuid("latex_project_id"),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _uuid("updated_by", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["latex_project_id"], ["latex_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("latex_project_id", "path", name="uq_document_file_project_path"),
    )
    op.create_index("ix_document_files_latex_project_id", "document_files", ["latex_project_id"])

    op.create_table(
        "latex_compile_jobs",
        _uuid("id", pk=True),
        _uuid("latex_project_id"),
        _uuid("project_id"),
        sa.Column("status", compile_status, nullable=False, server_default="queued"),
        sa.Column("engine", sa.String(50), nullable=False, server_default="mock"),
        sa.Column("log", sa.Text(), nullable=True),
        sa.Column("preview", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        _uuid("created_by"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["latex_project_id"], ["latex_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_latex_compile_jobs_latex_project_id", "latex_compile_jobs", ["latex_project_id"]
    )

    # --- skills ------------------------------------------------------------
    op.create_table(
        "skills",
        _uuid("id", pk=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("author", sa.String(120), nullable=False, server_default="researchos"),
        sa.Column("category", sa.String(60), nullable=False, server_default="general"),
        sa.Column("visibility", skill_visibility, nullable=False, server_default="first_party"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        _uuid("project_id", nullable=True),
        _uuid("created_by", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_skills_slug", "skills", ["slug"], unique=True)
    op.create_index("ix_skills_project_id", "skills", ["project_id"])

    op.create_table(
        "skill_versions",
        _uuid("id", pk=True),
        _uuid("skill_id"),
        sa.Column("version", sa.String(30), nullable=False, server_default="1.0.0"),
        sa.Column("manifest_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_version_skill_version"),
    )
    op.create_index("ix_skill_versions_skill_id", "skill_versions", ["skill_id"])

    op.create_table(
        "skill_installations",
        _uuid("id", pk=True),
        _uuid("project_id"),
        _uuid("skill_id"),
        _uuid("skill_version_id"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        _uuid("installed_by"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_version_id"], ["skill_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["installed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "skill_id", name="uq_skill_installation_project_skill"),
    )
    op.create_index("ix_skill_installations_project_id", "skill_installations", ["project_id"])
    op.create_index("ix_skill_installations_skill_id", "skill_installations", ["skill_id"])


def downgrade() -> None:
    for table in (
        "skill_installations",
        "skill_versions",
        "skills",
        "latex_compile_jobs",
        "document_files",
        "latex_projects",
        "experiment_artifacts",
        "experiment_logs",
        "experiment_metrics",
        "experiment_runs",
        "experiments",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    postgresql.ENUM(name="skill_visibility").drop(bind, checkfirst=True)
    postgresql.ENUM(name="compile_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="experiment_run_status").drop(bind, checkfirst=True)
    # 'experiment' / 'latex' remain in agent_type (PG cannot drop enum values).
