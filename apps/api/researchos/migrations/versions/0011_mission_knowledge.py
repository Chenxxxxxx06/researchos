"""add mission paper knowledge artifacts

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mission_topic_clusters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", "position", name="uq_mission_cluster_position"),
    )
    op.create_index(
        "ix_mission_topic_clusters_project_id", "mission_topic_clusters", ["project_id"]
    )
    op.create_index(
        "ix_mission_topic_clusters_mission_id", "mission_topic_clusters", ["mission_id"]
    )
    op.create_index(
        "ix_mission_clusters_project_mission",
        "mission_topic_clusters",
        ["project_id", "mission_id"],
    )

    op.create_table(
        "mission_papers",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("inclusion_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("included_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["mission_topic_clusters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["included_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", "paper_id", name="uq_mission_paper"),
    )
    op.create_index("ix_mission_papers_project_id", "mission_papers", ["project_id"])
    op.create_index("ix_mission_papers_mission_id", "mission_papers", ["mission_id"])
    op.create_index("ix_mission_papers_paper_id", "mission_papers", ["paper_id"])
    op.create_index("ix_mission_papers_cluster_id", "mission_papers", ["cluster_id"])
    op.create_index(
        "ix_mission_papers_project_mission", "mission_papers", ["project_id", "mission_id"]
    )

    op.create_table(
        "reading_cards",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("research_question", sa.Text(), nullable=False, server_default=""),
        sa.Column("method_flow_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("strengths_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("limitations_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("reproducibility_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("claims_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_by_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["research_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", "paper_id", name="uq_reading_card_mission_paper"),
    )
    op.create_index("ix_reading_cards_project_id", "reading_cards", ["project_id"])
    op.create_index("ix_reading_cards_mission_id", "reading_cards", ["mission_id"])
    op.create_index("ix_reading_cards_paper_id", "reading_cards", ["paper_id"])
    op.create_index(
        "ix_reading_cards_project_mission", "reading_cards", ["project_id", "mission_id"]
    )

    op.create_table(
        "reading_notes",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=True),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["paper_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reading_notes_project_id", "reading_notes", ["project_id"])
    op.create_index("ix_reading_notes_mission_id", "reading_notes", ["mission_id"])
    op.create_index("ix_reading_notes_paper_id", "reading_notes", ["paper_id"])
    op.create_index("ix_reading_notes_created_by", "reading_notes", ["created_by"])
    op.create_index("ix_reading_notes_project_paper", "reading_notes", ["project_id", "paper_id"])


def downgrade() -> None:
    op.drop_table("reading_notes")
    op.drop_table("reading_cards")
    op.drop_table("mission_papers")
    op.drop_table("mission_topic_clusters")
