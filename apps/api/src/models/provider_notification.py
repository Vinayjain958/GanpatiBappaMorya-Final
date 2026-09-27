from __future__ import annotations

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Index

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ProviderNotificationType = Enum(
    "BEHAVIORAL_MATCH", "BOOKING_REQUEST", "DEMAND_ALERT",
    name="provider_notification_type", native_enum=False,
)

class ProviderNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_notifications"

    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(ProviderNotificationType, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    experience_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="SET NULL"),
        nullable=True
    )
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # segment_summary: JSON list[str] — e.g. ["Culture & Heritage", "Mid-budget"]
    # Uses JSON column (same convention as TravelerInteraction.metadata_)
    segment_summary: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # PROVENANCE — exactly one of these is set per notification:
    # - Behavioral notification: source_event_id set, source_booking_request_id null
    # - Booking notification:    source_event_id null, source_booking_request_id set
    source_event_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    source_booking_request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("booking_requests.id", ondelete="SET NULL"),
        nullable=True
    )

    # Internal deduplication — NEVER exposed in API response
    traveler_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cooldown_key: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_provider_notifications_provider_read_created",
              "provider_id", "is_read", "created_at"),
        Index("ix_provider_notifications_provider_cooldown",
              "provider_id", "cooldown_key"),
        Index("ix_provider_notifications_source_booking",
              "source_booking_request_id"),
    )
