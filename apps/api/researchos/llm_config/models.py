"""LLM provider configuration — per-project, stored in DB.

Users manage these in Settings. Provider configs hold the type, custom base URL,
model name, and API key. Keys are stored as-is for MVP (a future improvement is
encryption at rest).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LLMProviderConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "llm_provider_configs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    provider_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="openai_compatible"
    )
    base_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="https://api.openai.com/v1"
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-4o")
    api_key: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
