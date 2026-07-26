"""Coding chat ORM models.

Sessions are UI/persistence objects that feed context into agent runs via
``input_json.context.chat_session_id``; runs stay single-shot and stateless
(P3-D6 intact), so ``agent_runs`` needs no session column.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from researchos.agents.enums import AgentType
from researchos.common.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # Reuses the existing native agent_type enum.
    agent_type: Mapped[AgentType] = mapped_column(
        _enum(AgentType, "agent_type"), nullable=False, default=AgentType.CODING
    )
    # First user message, truncated.
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.seq"
    )


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_chat_message_session_seq"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    patch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patch_proposals.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")
