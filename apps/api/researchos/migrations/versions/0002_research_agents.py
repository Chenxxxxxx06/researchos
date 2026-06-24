"""research copilot: papers, ideas, critiques, agent runs

Adds the Research Copilot schema: papers, ideas, research_critiques,
agent_runs, tool_calls, agent_run_events, plus the idea_status / agent_type /
agent_run_status / tool_call_status enums.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    idea_status = postgresql.ENUM("draft", "active", "archived", name="idea_status")
    agent_type = postgresql.ENUM("research", "critic", name="agent_type")
    agent_run_status = postgresql.ENUM(
        "queued", "running", "completed", "failed", "cancelled", name="agent_run_status"
    )
    tool_call_status = postgresql.ENUM("pending", "succeeded", "failed", name="tool_call_status")

    ts = lambda col: sa.Column(  # noqa: E731
        col, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # papers ----------------------------------------------------------------
    op.create_table(
        "papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("authors_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("venue", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), nullable=False),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "project_id", "source", "external_id", name="uq_paper_project_source_ext"
        ),
    )
    op.create_index("ix_papers_project_id", "papers", ["project_id"])
    op.create_index("ix_papers_imported_by", "papers", ["imported_by"])
    op.create_index("ix_papers_project_created", "papers", ["project_id", "created_at"])

    # ideas -----------------------------------------------------------------
    op.create_table(
        "ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("status", idea_status, nullable=False, server_default="draft"),
        sa.Column("novelty_score", sa.Float(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_ideas_project_id", "ideas", ["project_id"])
    op.create_index("ix_ideas_created_by", "ideas", ["created_by"])

    # agent_runs ------------------------------------------------------------
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_type", agent_type, nullable=False),
        sa.Column("status", agent_run_status, nullable=False, server_default="queued"),
        sa.Column("input_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_json", postgresql.JSONB(), nullable=True),
        sa.Column("token_usage_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("cost_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("skill_ids_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_project_created", "agent_runs", ["project_id", "created_at"])

    # research_critiques ----------------------------------------------------
    op.create_table(
        "research_critiques",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("novelty_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("weaknesses_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "missing_baselines_json", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("dataset_risks_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reproducibility_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("citations_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["idea_id"], ["ideas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_research_critiques_project_id", "research_critiques", ["project_id"])
    op.create_index("ix_research_critiques_idea_id", "research_critiques", ["idea_id"])
    op.create_index("ix_research_critiques_agent_run_id", "research_critiques", ["agent_run_id"])

    # tool_calls ------------------------------------------------------------
    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("arguments_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", tool_call_status, nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tool_calls_agent_run_id", "tool_calls", ["agent_run_id"])
    op.create_index("ix_tool_calls_project_id", "tool_calls", ["project_id"])
    op.create_index("ix_tool_calls_run_seq", "tool_calls", ["agent_run_id", "seq"])

    # agent_run_events ------------------------------------------------------
    op.create_table(
        "agent_run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        ts("created_at"),
        ts("updated_at"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_run_id", "seq", name="uq_agent_run_event_run_seq"),
    )
    op.create_index("ix_agent_run_events_agent_run_id", "agent_run_events", ["agent_run_id"])
    op.create_index("ix_agent_run_events_project_id", "agent_run_events", ["project_id"])


def downgrade() -> None:
    op.drop_table("agent_run_events")
    op.drop_table("tool_calls")
    op.drop_table("research_critiques")
    op.drop_table("agent_runs")
    op.drop_table("ideas")
    op.drop_table("papers")

    bind = op.get_bind()
    postgresql.ENUM(name="tool_call_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="agent_run_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="agent_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="idea_status").drop(bind, checkfirst=True)
