"""add durable research missions

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    mission_status = postgresql.ENUM(
        "draft", "active", "paused", "completed", "archived", name="mission_status"
    )
    mission_step_kind = postgresql.ENUM(
        "scope",
        "literature",
        "reading",
        "review",
        "experiment_plan",
        name="mission_step_kind",
    )
    mission_step_status = postgresql.ENUM(
        "locked",
        "ready",
        "in_progress",
        "needs_review",
        "completed",
        name="mission_step_status",
    )
    mission_status.create(bind, checkfirst=True)
    mission_step_kind.create(bind, checkfirst=True)
    mission_step_status.create(bind, checkfirst=True)

    status_type = postgresql.ENUM(name="mission_status", create_type=False)
    kind_type = postgresql.ENUM(name="mission_step_kind", create_type=False)
    step_status_type = postgresql.ENUM(name="mission_step_status", create_type=False)

    op.create_table(
        "research_missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(300), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("field", sa.String(120), nullable=True),
        sa.Column("status", status_type, nullable=False, server_default="draft"),
        sa.Column("current_step", kind_type, nullable=False, server_default="scope"),
        sa.Column(
            "scope_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_research_missions_project_id", "research_missions", ["project_id"])
    op.create_index("ix_research_missions_created_by", "research_missions", ["created_by"])
    op.create_index("ix_research_missions_updated_by", "research_missions", ["updated_by"])
    op.create_index(
        "ix_research_missions_project_activity",
        "research_missions",
        ["project_id", "last_activity_at"],
    )

    op.create_table(
        "mission_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_kind", kind_type, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", step_status_type, nullable=False),
        sa.Column(
            "input_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("mission_id", "step_kind", name="uq_mission_step_kind"),
    )
    op.create_index("ix_mission_steps_mission_id", "mission_steps", ["mission_id"])
    op.create_index("ix_mission_steps_project_id", "mission_steps", ["project_id"])
    op.create_index("ix_mission_steps_approved_by", "mission_steps", ["approved_by"])
    op.create_index(
        "ix_mission_steps_project_mission", "mission_steps", ["project_id", "mission_id"]
    )

    op.create_table(
        "mission_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "mission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("step_kind", kind_type, nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_mission_events_mission_id", "mission_events", ["mission_id"])
    op.create_index("ix_mission_events_project_id", "mission_events", ["project_id"])
    op.create_index("ix_mission_events_actor_id", "mission_events", ["actor_id"])
    op.create_index(
        "ix_mission_events_mission_created", "mission_events", ["mission_id", "created_at"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_mission_events_mission_created", table_name="mission_events")
    op.drop_index("ix_mission_events_actor_id", table_name="mission_events")
    op.drop_index("ix_mission_events_project_id", table_name="mission_events")
    op.drop_index("ix_mission_events_mission_id", table_name="mission_events")
    op.drop_table("mission_events")

    op.drop_index("ix_mission_steps_project_mission", table_name="mission_steps")
    op.drop_index("ix_mission_steps_approved_by", table_name="mission_steps")
    op.drop_index("ix_mission_steps_project_id", table_name="mission_steps")
    op.drop_index("ix_mission_steps_mission_id", table_name="mission_steps")
    op.drop_table("mission_steps")

    op.drop_index("ix_research_missions_project_activity", table_name="research_missions")
    op.drop_index("ix_research_missions_updated_by", table_name="research_missions")
    op.drop_index("ix_research_missions_created_by", table_name="research_missions")
    op.drop_index("ix_research_missions_project_id", table_name="research_missions")
    op.drop_table("research_missions")

    postgresql.ENUM(name="mission_step_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="mission_step_kind").drop(bind, checkfirst=True)
    postgresql.ENUM(name="mission_status").drop(bind, checkfirst=True)
