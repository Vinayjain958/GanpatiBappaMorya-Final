"""BookingRequest model (Phase 8).

REQUESTED intent only — no payment fields anywhere on this model, no
CONFIRMED status. A provider may ACCEPT or DECLINE a request; neither
state is ever presented to the traveler as a confirmed booking
(docs/DECISIONS.md ADR-046, docs/AI_CONTEXT.md hard invariant).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Index

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass

BookingRequestStatus = Enum(
    "REQUESTED", "ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED",
    name="booking_request_status", native_enum=False,
)


class BookingRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_requests"

    traveler_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("travelers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    itinerary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    itinerary_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("itinerary_items.id", ondelete="CASCADE"), nullable=False
    )
    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    traveler_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(BookingRequestStatus, default="REQUESTED", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_booking_requests_traveler_provider_experience_itinerary_status",
            "traveler_id", "provider_id", "experience_id", "itinerary_id", "status",
        ),
    )


__all__ = ["BookingRequest", "BookingRequestStatus"]
