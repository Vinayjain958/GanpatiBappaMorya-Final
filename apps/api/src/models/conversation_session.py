from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.conversation_message import ConversationMessage
    from src.models.user import User

ConversationMode = Enum("text", "voice", name="conversation_mode", native_enum=False)


class ConversationSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single conversational-discovery session, text or voice (Phase 5).

    `latest_traveler_context` is a denormalized JSON snapshot of the most
    recent structured TravelerContext — a single current value, not a
    history, so a JSON column is appropriate here (same pattern as
    Traveler.preferences). The append-only transcript itself lives in
    ConversationMessage rows, never crammed into this column — see
    docs/DECISIONS.md ADR-034. Audio is never stored anywhere.
    """

    __tablename__ = "conversation_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(ConversationMode, default="text", nullable=False)
    latest_traveler_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Phase 8: the authorized candidate-context cache for the
    # compose_experience tool — a JSON snapshot of the most recent
    # search_experiences ranked-and-feasible result for THIS conversation
    # (list of RankedExperienceItem dicts). compose_experience only ever
    # accepts experience_ids drawn from here; it is overwritten by every
    # new search_experiences call and never trusts raw ids Gemini supplies
    # directly (see src/services/ai_tools.py execute_compose_experience).
    last_search_candidates: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
