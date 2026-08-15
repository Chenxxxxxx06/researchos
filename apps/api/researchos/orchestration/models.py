"""ORM models for durable task graphs, leases, artifacts, gates, and events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MissionTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_tasks"
    __table_args__ = (
        UniqueConstraint("mission_id", "task_key", name="uq_mission_task_key"),
        UniqueConstraint("project_id", "idempotency_key", name="uq_mission_task_idempotency"),
        Index("ix_mission_tasks_runnable", "project_id", "status", "available_at", "priority"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mission_steps.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    acceptance_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    permissions_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    budget_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MissionTaskDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_mission_task_dependency"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    required_artifact_schema: Mapped[str | None] = mapped_column(String(160), nullable=True)


class TaskLease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_leases"
    __table_args__ = (UniqueConstraint("task_id", name="uq_task_lease_task"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    token: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4, unique=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class TaskArtifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_artifacts"
    __table_args__ = (
        UniqueConstraint("task_id", "schema_name", "content_hash", name="uq_task_artifact_content"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_name: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_artifact_versions_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    producer_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="team")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_artifacts.id", ondelete="SET NULL"), nullable=True
    )


class ApprovalGate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_gates"
    __table_args__ = (UniqueConstraint("task_id", "gate_kind", name="uq_task_approval_gate_kind"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gate_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    request_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    decision_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_events"
    __table_args__ = (UniqueConstraint("task_id", "seq", name="uq_task_event_seq"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchLoop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_loops"
    __table_args__ = (
        Index("ix_research_loops_mission_status", "mission_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric_direction: Mapped[str] = mapped_column(String(8), nullable=False)
    metric_aggregation: Mapped[str] = mapped_column(String(16), nullable=False, default="final")
    baseline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    best_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    baseline_metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    best_metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    fixed_budget_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    patience: Mapped[int] = mapped_column(Integer, nullable=False)
    min_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_complexity_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    critic_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    current_iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_improvement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    editable_scope_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    protected_scope_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    stop_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class ResearchLoopIteration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_loop_iterations"
    __table_args__ = (
        UniqueConstraint("loop_id", "iteration_number", name="uq_research_loop_iteration"),
        Index("ix_research_loop_iterations_status", "loop_id", "status"),
    )

    loop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_loops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    component: Mapped[str] = mapped_column(String(120), nullable=False)
    expected_effect: Mapped[str] = mapped_column(Text, nullable=False)
    changed_paths_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    patch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patch_proposals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    experiment_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    improvement: Mapped[float | None] = mapped_column(Float, nullable=True)
    complexity_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    critic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rule_checks_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    decision_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
