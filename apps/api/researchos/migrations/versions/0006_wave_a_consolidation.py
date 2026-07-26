"""wave A consolidation: chat, revisions, suggestions, sections, anchors, figures, prefs

Single consolidated migration for the Wave A partitions (CONSOLIDATION §6.1):

(a) tool_calls seq renumber backfill + uq_tool_call_run_seq;
(b) patch_files/base_content+edits_json, patch_proposals apply/conflict columns,
    new chat_sessions + chat_messages;
(c) new document_file_revisions (+backfill), document_suggestion_op/status
    enums + document_suggestions, latex_compile_jobs preview/diagnostics;
(d) paper_ingest_status/paper_section_kind enums, papers ingest columns
    (+backfills, +2 indexes), ideas.metadata_json, paper_sections,
    research_feed_prefs;
(e) experiments.metric_meta_json, experiment_runs.log_next_seq (+backfill),
    experiment_logs resequence backfill + uq_experiment_logs_run_seq,
    anchor_aggregation/figure_render_status enums, result_anchors, figures,
    figure_assets, user_preferences (UNIQUE NULLS NOT DISTINCT, PG16),
    experiment_ingest_tokens.

Backfills always run before the unique constraints they satisfy.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(col: str) -> sa.Column:
    return sa.Column(col, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _uuid(col: str, *, nullable: bool = False, pk: bool = False) -> sa.Column:
    return sa.Column(col, postgresql.UUID(as_uuid=True), primary_key=pk, nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()

    # --- (a) tool_calls: renumber duplicate seqs, then enforce uniqueness ----
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY agent_run_id ORDER BY created_at, id
                   ) - 1 AS new_seq
            FROM tool_calls
        )
        UPDATE tool_calls AS tc
        SET seq = ranked.new_seq
        FROM ranked
        WHERE tc.id = ranked.id AND tc.seq IS DISTINCT FROM ranked.new_seq
        """
    )
    # The non-unique composite index is superseded by the unique constraint.
    op.drop_index("ix_tool_calls_run_seq", table_name="tool_calls")
    op.create_unique_constraint("uq_tool_call_run_seq", "tool_calls", ["agent_run_id", "seq"])

    # --- (b) patches: review/apply metadata ----------------------------------
    op.add_column("patch_files", sa.Column("base_content", sa.Text(), nullable=True))
    op.add_column("patch_files", sa.Column("edits_json", postgresql.JSONB(), nullable=True))
    op.add_column(
        "patch_proposals", sa.Column("applied_commit_sha", sa.String(64), nullable=True)
    )
    op.add_column("patch_proposals", sa.Column("conflict_json", postgresql.JSONB(), nullable=True))
    op.add_column(
        "patch_proposals",
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        None,
        "patch_proposals",
        "patch_proposals",
        ["superseded_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- (b) coding chat -----------------------------------------------------
    # chat_sessions.agent_type reuses the existing native agent_type enum.
    agent_type = postgresql.ENUM(name="agent_type", create_type=False)
    op.create_table(
        "chat_sessions",
        _uuid("id", pk=True),
        _uuid("project_id"),
        _uuid("created_by"),
        sa.Column("agent_type", agent_type, nullable=False, server_default="coding"),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_chat_sessions_project_id", "chat_sessions", ["project_id"])

    op.create_table(
        "chat_messages",
        _uuid("id", pk=True),
        _uuid("session_id"),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _uuid("agent_run_id", nullable=True),
        _uuid("patch_id", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patch_id"], ["patch_proposals.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("session_id", "seq", name="uq_chat_message_session_seq"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    # --- (c) document file revisions (+ backfill current versions) -----------
    op.create_table(
        "document_file_revisions",
        _uuid("id", pk=True),
        _uuid("document_file_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _uuid("updated_by", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["document_file_id"], ["document_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "document_file_id", "version", name="uq_document_revision_file_version"
        ),
    )
    op.create_index(
        "ix_document_file_revisions_document_file_id",
        "document_file_revisions",
        ["document_file_id"],
    )
    # One revision per existing file at its current version (CAS merge base).
    op.execute(
        """
        INSERT INTO document_file_revisions
            (id, document_file_id, version, content, updated_by, created_at, updated_at)
        SELECT gen_random_uuid(), df.id, df.version, df.content, df.updated_by,
               df.updated_at, df.updated_at
        FROM document_files AS df
        """
    )

    # --- (c) document suggestions --------------------------------------------
    document_suggestion_op = postgresql.ENUM(
        "rewrite",
        "expand",
        "condense",
        "fix_grammar",
        "continue_writing",
        "custom",
        name="document_suggestion_op",
    )
    document_suggestion_status = postgresql.ENUM(
        "proposed", "accepted", "rejected", "superseded", name="document_suggestion_status"
    )
    op.create_table(
        "document_suggestions",
        _uuid("id", pk=True),
        _uuid("latex_project_id"),
        _uuid("document_file_id"),
        _uuid("agent_run_id", nullable=True),
        sa.Column("op", document_suggestion_op, nullable=False),
        sa.Column(
            "status", document_suggestion_status, nullable=False, server_default="proposed"
        ),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("anchor_mode", sa.String(10), nullable=False, server_default="range"),
        sa.Column("range_json", postgresql.JSONB(), nullable=False),
        sa.Column("old_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("spans_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_error", sa.String(50), nullable=True),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        _uuid("created_by"),
        _uuid("resolved_by", nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["latex_project_id"], ["latex_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_file_id"], ["document_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_document_suggestions_latex_project_id", "document_suggestions", ["latex_project_id"]
    )
    op.create_index(
        "ix_document_suggestions_document_file_id", "document_suggestions", ["document_file_id"]
    )
    op.create_index(
        "ix_document_suggestions_agent_run_id", "document_suggestions", ["agent_run_id"]
    )
    op.create_index("ix_document_suggestions_created_by", "document_suggestions", ["created_by"])
    op.create_index(
        "ix_document_suggestions_project_status",
        "document_suggestions",
        ["latex_project_id", "status"],
    )

    # --- (c) latex compile jobs: structural preview + diagnostics ------------
    op.add_column(
        "latex_compile_jobs", sa.Column("preview_model_json", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "latex_compile_jobs",
        sa.Column("diagnostics_json", postgresql.JSONB(), nullable=False, server_default="[]"),
    )

    # --- (d) papers: ingest columns, indexes, backfills ----------------------
    paper_ingest_status = postgresql.ENUM(
        "pending", "running", "succeeded", "abstract_only", "failed", name="paper_ingest_status"
    )
    paper_ingest_status.create(bind, checkfirst=True)

    op.add_column("papers", sa.Column("doi", sa.String(255), nullable=True))
    op.add_column("papers", sa.Column("arxiv_id", sa.String(64), nullable=True))
    op.add_column("papers", sa.Column("primary_category", sa.String(32), nullable=True))
    op.add_column("papers", sa.Column("citation_count", sa.Integer(), nullable=True))
    op.add_column(
        "papers",
        sa.Column(
            "ingest_status",
            postgresql.ENUM(name="paper_ingest_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("papers", sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("papers", sa.Column("ingest_error", sa.Text(), nullable=True))
    op.create_index("ix_papers_project_doi", "papers", ["project_id", "doi"])
    op.create_index("ix_papers_project_arxiv", "papers", ["project_id", "arxiv_id"])
    op.execute("UPDATE papers SET arxiv_id = external_id WHERE source = 'arxiv'")
    op.execute(
        """
        UPDATE papers
        SET doi = lower(metadata_json->>'doi')
        WHERE metadata_json->>'doi' IS NOT NULL
        """
    )

    # --- (d) ideas: gap-generation metadata ----------------------------------
    op.add_column(
        "ideas",
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
    )

    # --- (d) paper sections --------------------------------------------------
    paper_section_kind = postgresql.ENUM(
        "abstract",
        "introduction",
        "background",
        "method",
        "experiments",
        "results",
        "related_work",
        "conclusion",
        "appendix",
        "other",
        name="paper_section_kind",
    )
    op.create_table(
        "paper_sections",
        _uuid("id", pk=True),
        _uuid("paper_id"),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("heading", sa.String(500), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("kind", paper_section_kind, nullable=False, server_default="other"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("paper_id", "seq", name="uq_paper_section_seq"),
    )
    op.create_index("ix_paper_sections_paper_id", "paper_sections", ["paper_id"])

    # --- (d) research feed prefs ---------------------------------------------
    op.create_table(
        "research_feed_prefs",
        _uuid("project_id", pk=True),
        sa.Column("categories", postgresql.JSONB(), nullable=False, server_default="[]"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )

    # --- (e) experiments: metric metadata + log sequencing -------------------
    op.add_column(
        "experiments",
        sa.Column("metric_meta_json", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "experiment_runs",
        sa.Column("log_next_seq", sa.Integer(), nullable=False, server_default="0"),
    )
    # Resequence logs per run (stable by prior seq, then insertion order) so the
    # unique constraint below always holds; runs BEFORE the constraint.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY run_id ORDER BY seq, created_at, id
                   ) - 1 AS new_seq
            FROM experiment_logs
        )
        UPDATE experiment_logs AS el
        SET seq = ranked.new_seq
        FROM ranked
        WHERE el.id = ranked.id AND el.seq IS DISTINCT FROM ranked.new_seq
        """
    )
    op.create_unique_constraint(
        "uq_experiment_logs_run_seq", "experiment_logs", ["run_id", "seq"]
    )
    # After resequencing, seqs are 0..n-1, so the next seq is the count.
    op.execute(
        """
        UPDATE experiment_runs AS er
        SET log_next_seq = sub.log_count
        FROM (
            SELECT run_id, COUNT(*) AS log_count FROM experiment_logs GROUP BY run_id
        ) AS sub
        WHERE er.id = sub.run_id
        """
    )

    # --- (e) result anchors --------------------------------------------------
    anchor_aggregation = postgresql.ENUM(
        "final", "best", "min", "max", "mean", name="anchor_aggregation"
    )
    op.create_table(
        "result_anchors",
        _uuid("id", pk=True),
        _uuid("project_id"),
        sa.Column("name", sa.String(64), nullable=False),
        _uuid("experiment_id"),
        _uuid("run_id", nullable=True),
        sa.Column("metric_name", sa.String(120), nullable=False),
        sa.Column("aggregation", anchor_aggregation, nullable=False, server_default="final"),
        sa.Column("decimals", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("scale", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("suffix", sa.String(16), nullable=False, server_default=""),
        sa.Column("captured_value", sa.Float(), nullable=True),
        _uuid("captured_run_id", nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        _uuid("created_by"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["captured_run_id"], ["experiment_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "name", name="uq_result_anchors_project_name"),
    )
    op.create_index("ix_result_anchors_project_id", "result_anchors", ["project_id"])
    op.create_index("ix_result_anchors_experiment_id", "result_anchors", ["experiment_id"])
    op.create_index("ix_result_anchors_created_by", "result_anchors", ["created_by"])

    # --- (e) figures + rendered assets ---------------------------------------
    figure_render_status = postgresql.ENUM(
        "pending", "rendering", "rendered", "failed", name="figure_render_status"
    )
    op.create_table(
        "figures",
        _uuid("id", pk=True),
        _uuid("project_id"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", figure_render_status, nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("rendered_style_slug", sa.String(64), nullable=True),
        sa.Column("rendered_style_version", sa.String(16), nullable=True),
        sa.Column("source_run_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_rendered_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("latex_project_id", nullable=True),
        sa.Column("usage_path", sa.String(512), nullable=True),
        _uuid("created_by"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["latex_project_id"], ["latex_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "name", name="uq_figures_project_name"),
    )
    op.create_index("ix_figures_project_id", "figures", ["project_id"])
    op.create_index("ix_figures_created_by", "figures", ["created_by"])

    op.create_table(
        "figure_assets",
        _uuid("id", pk=True),
        _uuid("figure_id"),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["figure_id"], ["figures.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("figure_id", "format", name="uq_figure_assets_figure_format"),
    )
    op.create_index("ix_figure_assets_figure_id", "figure_assets", ["figure_id"])

    # --- (e) user preferences (PG16: UNIQUE NULLS NOT DISTINCT) --------------
    op.create_table(
        "user_preferences",
        _uuid("id", pk=True),
        _uuid("user_id"),
        _uuid("project_id", nullable=True),
        sa.Column("theme", sa.String(16), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("figure_style_slug", sa.String(64), nullable=True),
        sa.Column("extra_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id",
            "project_id",
            name="uq_user_preferences_user_project",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

    # --- (e) experiment ingest tokens ----------------------------------------
    op.create_table(
        "experiment_ingest_tokens",
        _uuid("id", pk=True),
        _uuid("project_id"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.CHAR(64), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(12), nullable=False),
        _uuid("created_by"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_experiment_ingest_tokens_project_id", "experiment_ingest_tokens", ["project_id"]
    )
    op.create_index(
        "ix_experiment_ingest_tokens_created_by", "experiment_ingest_tokens", ["created_by"]
    )


def downgrade() -> None:
    bind = op.get_bind()

    # --- (e) reversals -------------------------------------------------------
    op.drop_table("experiment_ingest_tokens")
    op.drop_table("user_preferences")
    op.drop_table("figure_assets")
    op.drop_table("figures")
    op.drop_table("result_anchors")
    postgresql.ENUM(name="figure_render_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="anchor_aggregation").drop(bind, checkfirst=True)
    op.drop_constraint("uq_experiment_logs_run_seq", "experiment_logs", type_="unique")
    op.drop_column("experiment_runs", "log_next_seq")
    op.drop_column("experiments", "metric_meta_json")

    # --- (d) reversals -------------------------------------------------------
    op.drop_table("research_feed_prefs")
    op.drop_table("paper_sections")
    postgresql.ENUM(name="paper_section_kind").drop(bind, checkfirst=True)
    op.drop_column("ideas", "metadata_json")
    op.drop_index("ix_papers_project_arxiv", table_name="papers")
    op.drop_index("ix_papers_project_doi", table_name="papers")
    op.drop_column("papers", "ingest_error")
    op.drop_column("papers", "ingested_at")
    op.drop_column("papers", "ingest_status")
    op.drop_column("papers", "citation_count")
    op.drop_column("papers", "primary_category")
    op.drop_column("papers", "arxiv_id")
    op.drop_column("papers", "doi")
    postgresql.ENUM(name="paper_ingest_status").drop(bind, checkfirst=True)

    # --- (c) reversals -------------------------------------------------------
    op.drop_column("latex_compile_jobs", "diagnostics_json")
    op.drop_column("latex_compile_jobs", "preview_model_json")
    op.drop_table("document_suggestions")
    postgresql.ENUM(name="document_suggestion_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="document_suggestion_op").drop(bind, checkfirst=True)
    op.drop_table("document_file_revisions")

    # --- (b) reversals -------------------------------------------------------
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    # Dropping the column drops its (auto-named) self-referencing FK with it.
    op.drop_column("patch_proposals", "superseded_by")
    op.drop_column("patch_proposals", "conflict_json")
    op.drop_column("patch_proposals", "applied_commit_sha")
    op.drop_column("patch_files", "edits_json")
    op.drop_column("patch_files", "base_content")

    # --- (a) reversals -------------------------------------------------------
    op.drop_constraint("uq_tool_call_run_seq", "tool_calls", type_="unique")
    op.create_index("ix_tool_calls_run_seq", "tool_calls", ["agent_run_id", "seq"])
