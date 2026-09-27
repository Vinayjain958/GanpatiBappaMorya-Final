"""ItineraryRevision model (Phase 9).

Every successful replan (automatic or manual) creates exactly one new
ItineraryRevision row and increments Itinerary.version by 1 — history is
never overwritten (docs/AI_CONTEXT.md hard invariant: every replan
creates a traceable revision). `changes` is a normalized JSON summary
(added/removed/moved/unchanged/affected item ids) — never raw external
API payloads.

`idempotency_key` + a unique constraint on (itinerary_id,
idempotency_key) implement the minimal idempotency pattern the Phase 9
spec asks for: a repeated identical replan request short-circuits to the
prior revision's result instead of creating a duplicate row.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Index, UniqueConstraint

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass

ReplanTrigger = Enum(
    "USER_REQUESTED", "TIME_CHANGED", "BUDGET_CHANGED", "PARTY_SIZE_CHANGED",
    "WEATHER_CHANGED", "EVENT_CANCELLED", "EVENT_RESCHEDULED", "EVENT_VENUE_CHANGED",
    "AVAILABILITY_CHANGED",
    name="replan_trigger", native_enum=False,
)
RevisionStatus = Enum(
    "REPLANNED", "NO_CHANGE", "REPLAN_FAILED", "REQUIRES_USER_ACTION",
    name="itinerary_revision_status", native_enum=False,
)


class ItineraryRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "itinerary_revisions"

    itinerary_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger: Mapped[str] = mapped_column(ReplanTrigger, nullable=False)
    status: Mapped[str] = mapped_column(RevisionStatus, nullable=False)

    # Normalized change set: {"added_items": [...], "removed_items": [...],
    # "moved_items": [...], "unchanged_items": [...], "affected_items": [...]}
    changes: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    context_snapshot_reference: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("itinerary_id", "idempotency_key", name="uq_itinerary_revision_idempotency"),
        Index("ix_itinerary_revisions_itinerary_id_version", "itinerary_id", "version"),
    )


__all__ = ["ItineraryRevision", "ReplanTrigger", "RevisionStatus"]
