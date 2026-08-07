"""add structured review documents, sections, and versions

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_documents",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="outline"),
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
        sa.UniqueConstraint("mission_id", name="uq_review_document_mission"),
    )
    op.create_index("ix_review_documents_project_id", "review_documents", ["project_id"])
    op.create_index("ix_review_documents_mission_id", "review_documents", ["mission_id"])
    op.create_table(
        "review_sections",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("citations_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("claims_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="outline"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generated_by_run_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["review_id"], ["review_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "section_key", name="uq_review_section_key"),
    )
    for column in ("project_id", "mission_id", "review_id"):
        op.create_index(f"ix_review_sections_{column}", "review_sections", [column])
    op.create_index(
        "ix_review_sections_mission_position", "review_sections", ["mission_id", "position"]
    )
    op.create_table(
        "review_versions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["review_id"], ["review_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "version", name="uq_review_version"),
    )
    for column in ("project_id", "mission_id", "review_id"):
        op.create_index(f"ix_review_versions_{column}", "review_versions", [column])
    op.create_index(
        "ix_review_versions_project_review", "review_versions", ["project_id", "review_id"]
    )


def downgrade() -> None:
    op.drop_table("review_versions")
    op.drop_table("review_sections")
    op.drop_table("review_documents")
