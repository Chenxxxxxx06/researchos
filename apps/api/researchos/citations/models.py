"""Persisted citation audit reports."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MissionCitationAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_citation_audits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    items_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    duplicate_groups_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bibtex_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
