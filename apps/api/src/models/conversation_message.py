from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.conversation_session import ConversationSession

ConversationRole = Enum("user", "assistant", name="conversation_role", native_enum=False)


class ConversationMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single transcript turn. `text` holds transcript text only — for
    voice turns this is Gemini's input/output transcription text, never
    raw audio (docs/DECISIONS.md ADR-034 — audio is never persisted).
    `tool_call_metadata` records which tool ran and a result summary
    (name/args/result_count) for observability, not internal exception
    detail or database internals.
    """

    __tablename__ = "conversation_messages"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(ConversationRole, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tool_call_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    session: Mapped[ConversationSession] = relationship(back_populates="messages")
