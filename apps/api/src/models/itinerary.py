"""Itinerary model (Phase 8).

An Itinerary is the persisted result of the deterministic composer
(src/services/experience_composer.py) plus its Gemini narrative. It always
belongs to exactly one traveler; items are only reachable through an
itinerary the authenticated traveler owns (see src/api/v1/itineraries.py).

`status` lifecycle: DRAFT (composed, not yet validated) -> VALIDATED
(passed itinerary_validator.py) -> BOOKING_REQUESTED (at least one
BookingRequest exists) -> COMPLETED/CANCELLED. Never CONFIRMED — booking
is REQUESTED intent only (docs/DECISIONS.md ADR-046).

`ranking_model_version`/`narrative_model_version` are distinct from each
other on purpose: ranking_model_version mirrors Phase 7's
Settings.ranking_model_version ("weighted-v1"); narrative_model_version
identifies the (also non-authoritative) Gemini narrative layer
("gemini-narrative-v1" or "template-fallback-v1" when Gemini failed) —
neither ever decides feasibility or itinerary validity.
"""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime
from datetime import time as time_
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Index

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.itinerary_custom_activity import ItineraryCustomActivity
    from src.models.itinerary_item import ItineraryItem
    from src.models.traveler import Traveler

ItineraryStatus = Enum(
    "DRAFT", "VALIDATED", "BOOKING_REQUESTED", "COMPLETED", "CANCELLED",
    name="itinerary_status", native_enum=False,
)
ItinerarySource = Enum("COMPOSER", "MANUAL", name="itinerary_source", native_enum=False)


class Itinerary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "itineraries"

    traveler_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("travelers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    itinerary_date: Mapped[date_] = mapped_column(Date, nullable=False)
    start_time: Mapped[time_] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(ItineraryStatus, default="DRAFT", nullable=False)
    source: Mapped[str] = mapped_column(ItinerarySource, default="COMPOSER", nullable=False)

    total_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_travel_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Retained for additive custom-activity budget checks.
    max_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # Gemini-generated narrative (facts-only, backend-validated inputs —
    # see src/services/itinerary_narrator.py). Nullable: narrative
    # generation failure never invalidates an otherwise-valid itinerary.
    narrative_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    narrative_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_closing_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    ranking_model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    narrative_model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── Phase 9: versioning, replanning, context freshness ──────────────
    # `version` is the optimistic-locking counter: every successful
    # replan increments it by exactly 1 and records an ItineraryRevision
    # (src/models/itinerary_revision.py). Manual/automatic replan requests
    # must supply `expected_version`; a mismatch is a 409
    # ITINERARY_VERSION_CONFLICT (see src/services/replanning.py) —
    # never a silent overwrite of a concurrently-updated itinerary.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    replanning_status: Mapped[str] = mapped_column(
        String(30), default="STABLE", nullable=False
    )  # STABLE | REPLANNING | REQUIRES_USER_ACTION
    context_last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    traveler: Mapped[Traveler] = relationship()
    items: Mapped[list[ItineraryItem]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="ItineraryItem.sequence_order",
    )
    custom_activities: Mapped[list[ItineraryCustomActivity]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="ItineraryCustomActivity.sequence_order",
    )

    __table_args__ = (
        Index("ix_itineraries_traveler_id_date_status", "traveler_id", "itinerary_date", "status"),
    )


__all__ = ["Itinerary", "ItinerarySource", "ItineraryStatus"]
