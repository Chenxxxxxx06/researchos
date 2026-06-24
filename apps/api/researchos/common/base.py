"""Declarative base for SQLAlchemy ORM models.

Phase 0 intentionally defines **no** business tables. This base exists so that
Alembic has a stable ``metadata`` target and later phases can attach models
without restructuring migrations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ResearchOS ORM models."""


class UUIDPrimaryKeyMixin:
    """Application-side UUID primary key (see PHASE1_DECISIONS P1-D10)."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Created/updated timestamps managed by the database server clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Aggregated model metadata for Alembic autogeneration. The aggregator module
# (researchos.models) imports every model so they register on this metadata.
metadata = Base.metadata
