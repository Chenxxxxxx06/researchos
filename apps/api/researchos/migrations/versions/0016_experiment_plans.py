"""add structured experiment plans and planner agent

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'experiment_planner'")
    op.create_table(
        "experiment_plans",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("research_gap", sa.Text(), nullable=False, server_default=""),
        sa.Column("hypothesis", sa.Text(), nullable=False, server_default=""),
        sa.Column("variables_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("baselines_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("datasets_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("metrics_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("matrix_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("decision_rules_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("stop_conditions_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risks_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reproducibility_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_by_run_id", sa.Uuid(), nullable=True),
        sa.Column("published_experiment_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["published_experiment_id"], ["experiments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", name="uq_experiment_plan_mission"),
    )
    op.create_index("ix_experiment_plans_project_id", "experiment_plans", ["project_id"])
    op.create_index("ix_experiment_plans_mission_id", "experiment_plans", ["mission_id"])
    op.create_table(
        "experiment_plan_versions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["experiment_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "version", name="uq_experiment_plan_version"),
    )
    for column in ("project_id", "mission_id", "plan_id"):
        op.create_index(
            f"ix_experiment_plan_versions_{column}", "experiment_plan_versions", [column]
        )
    op.create_index(
        "ix_experiment_plan_versions_project_plan",
        "experiment_plan_versions",
        ["project_id", "plan_id"],
    )


def downgrade() -> None:
    op.drop_table("experiment_plan_versions")
    op.drop_table("experiment_plans")
