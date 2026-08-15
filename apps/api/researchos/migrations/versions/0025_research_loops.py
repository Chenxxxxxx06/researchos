"""bounded autonomous research loops

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "research_loops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("metric_name", sa.String(120), nullable=False),
        sa.Column("metric_direction", sa.String(8), nullable=False),
        sa.Column("metric_aggregation", sa.String(16), nullable=False, server_default="final"),
        sa.Column("baseline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("best_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("baseline_metric_value", sa.Float(), nullable=False),
        sa.Column("best_metric_value", sa.Float(), nullable=False),
        sa.Column("fixed_budget_seconds", sa.Integer(), nullable=False),
        sa.Column("max_iterations", sa.Integer(), nullable=False),
        sa.Column("patience", sa.Integer(), nullable=False),
        sa.Column("min_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_complexity_delta", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("critic_threshold", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("current_iteration", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_improvement_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "editable_scope_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "protected_scope_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("stop_reason", sa.String(120)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["baseline_run_id"], ["experiment_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["best_run_id"], ["experiment_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    for name in ("project_id", "mission_id", "task_id", "baseline_run_id", "best_run_id"):
        op.create_index(f"ix_research_loops_{name}", "research_loops", [name])
    op.create_index(
        "ix_research_loops_mission_status", "research_loops", ["mission_id", "status"]
    )

    op.create_table(
        "research_loop_iterations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("loop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("iteration_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="proposed"),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("component", sa.String(120), nullable=False),
        sa.Column("expected_effect", sa.Text(), nullable=False),
        sa.Column(
            "changed_paths_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("patch_id", postgresql.UUID(as_uuid=True)),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("experiment_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("code_commit_sha", sa.String(64)),
        sa.Column("metric_value", sa.Float()),
        sa.Column("improvement", sa.Float()),
        sa.Column("complexity_delta", sa.Integer()),
        sa.Column("critic_score", sa.Float()),
        sa.Column(
            "rule_checks_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "decision_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["loop_id"], ["research_loops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patch_id"], ["patch_proposals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["experiment_run_id"], ["experiment_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("loop_id", "iteration_number", name="uq_research_loop_iteration"),
    )
    for name in (
        "loop_id",
        "project_id",
        "mission_id",
        "task_id",
        "patch_id",
        "agent_run_id",
        "experiment_run_id",
    ):
        op.create_index(
            f"ix_research_loop_iterations_{name}", "research_loop_iterations", [name]
        )
    op.create_index(
        "ix_research_loop_iterations_status",
        "research_loop_iterations",
        ["loop_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("research_loop_iterations")
    op.drop_table("research_loops")
