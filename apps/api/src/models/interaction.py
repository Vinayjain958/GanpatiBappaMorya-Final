from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Index, UniqueConstraint

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience
    from src.models.traveler import Traveler

class TravelerInteraction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Behavioral interaction event for a traveler (e.g. SAVE, COMPLETE)."""

    __tablename__ = "traveler_interactions"

    traveler_id: Mapped[str] = mapped_column(String(36), ForeignKey("travelers.id", ondelete="CASCADE"), nullable=False, index=True)
    experience_id: Mapped[str] = mapped_column(String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    client_event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    recommendation_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    traveler: Mapped[Traveler] = relationship(back_populates="interactions")
    experience: Mapped[Experience] = relationship(back_populates="interactions")

    __table_args__ = (
        UniqueConstraint("traveler_id", "client_event_id", name="uq_traveler_interaction_client_event"),
        Index("ix_traveler_interactions_traveler_id_created_at", "traveler_id", "created_at"),
        Index("ix_traveler_interactions_traveler_id_event_type", "traveler_id", "event_type"),
    )
