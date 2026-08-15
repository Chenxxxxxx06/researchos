"""durable mission task DAG control plane

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
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
        "mission_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_step_id", postgresql.UUID(as_uuid=True)),
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("task_key", sa.String(120), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("role", sa.String(80), nullable=False),
        sa.Column("agent_type", sa.String(50)),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(300), nullable=False),
        sa.Column(
            "input_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "output_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "acceptance_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "permissions_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "budget_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_json", postgresql.JSONB()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_step_id"], ["mission_steps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["mission_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("mission_id", "task_key", name="uq_mission_task_key"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_mission_task_idempotency"),
    )
    for name in (
        "project_id",
        "mission_id",
        "mission_step_id",
        "parent_task_id",
        "agent_run_id",
        "created_by",
    ):
        op.create_index(f"ix_mission_tasks_{name}", "mission_tasks", [name])
    op.create_index(
        "ix_mission_tasks_runnable",
        "mission_tasks",
        ["project_id", "status", "available_at", "priority"],
    )

    op.create_table(
        "mission_task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("required_artifact_schema", sa.String(160)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_mission_task_dependency"),
    )
    for name in ("project_id", "mission_id", "task_id", "depends_on_task_id"):
        op.create_index(f"ix_mission_task_dependencies_{name}", "mission_task_dependencies", [name])

    op.create_table(
        "task_leases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("token", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("task_id", name="uq_task_lease_task"),
    )
    for name in ("project_id", "mission_id", "task_id", "expires_at"):
        op.create_index(f"ix_task_leases_{name}", "task_leases", [name])

    op.create_table(
        "task_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_name", sa.String(160), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("uri", sa.String(2048)),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "input_artifact_versions_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("producer_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visibility", sa.String(30), nullable=False, server_default="team"),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producer_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["task_artifacts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "task_id", "schema_name", "content_hash", name="uq_task_artifact_content"
        ),
    )
    for name in ("project_id", "mission_id", "task_id", "producer_run_id", "created_by"):
        op.create_index(f"ix_task_artifacts_{name}", "task_artifacts", [name])

    op.create_table(
        "approval_gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gate_kind", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column(
            "request_json",
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
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("task_id", "gate_kind", name="uq_task_approval_gate_kind"),
    )
    for name in ("project_id", "mission_id", "task_id"):
        op.create_index(f"ix_approval_gates_{name}", "approval_gates", [name])

    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("message", sa.Text()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["mission_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("task_id", "seq", name="uq_task_event_seq"),
    )
    for name in ("project_id", "mission_id", "task_id"):
        op.create_index(f"ix_task_events_{name}", "task_events", [name])


def downgrade() -> None:
    op.drop_table("task_events")
    op.drop_table("approval_gates")
    op.drop_table("task_artifacts")
    op.drop_table("task_leases")
    op.drop_table("mission_task_dependencies")
    op.drop_table("mission_tasks")
