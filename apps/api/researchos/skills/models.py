"""Skill ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from .enums import SkillVisibility


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(String(120), nullable=False, default="researchos")
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="general")
    visibility: Mapped[SkillVisibility] = mapped_column(
        Enum(
            SkillVisibility,
            name="skill_visibility",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=SkillVisibility.FIRST_PARTY,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    # Custom skills belong to a project; first-party skills are global (null).
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SkillVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_version_skill_version"),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0.0")
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class SkillInstallation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skill_installations"
    __table_args__ = (
        UniqueConstraint("project_id", "skill_id", name="uq_skill_installation_project_skill"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill_versions.id", ondelete="RESTRICT"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    installed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
