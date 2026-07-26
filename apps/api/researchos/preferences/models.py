"""User preference ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per (user, scope); ``project_id NULL`` is the user's global row.

    NULL in a value column means "no opinion at this scope" — resolution falls
    through project -> global -> defaults.
    """

    __tablename__ = "user_preferences"
    __table_args__ = (
        # One global row and one row per project per user (PG15+ semantics).
        UniqueConstraint(
            "user_id",
            "project_id",
            name="uq_user_preferences_user_project",
            postgresql_nulls_not_distinct=True,
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    theme: Mapped[str | None] = mapped_column(String(16), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    figure_style_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
