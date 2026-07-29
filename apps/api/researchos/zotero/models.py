"""Persistent Zotero connection state.

The imported bibliographic records live in the canonical ``papers`` table.
This row only stores connection and incremental-sync metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ZoteroConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "zotero_connections"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_zotero_connection_project"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    library_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    library_id: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_collections_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_library_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
