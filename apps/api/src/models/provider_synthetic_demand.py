from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Index

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProviderSyntheticDemandSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pre-aggregated synthetic demand for provider analytics demonstration.

    Isolated from TravelerInteraction and TravelerAffinity — seeded by
    scripts/seed_provider_intelligence.py only. Never created by any
    live API endpoint. ProviderInsightService reads this alongside
    observed aggregates but keeps them separate in the response
    (InsightProvenance.has_synthetic_data flag).
    """
    __tablename__ = "provider_synthetic_demand_snapshots"

    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    experience_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="SET NULL"),
        nullable=True
    )

    # Time window this snapshot covers
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Demand aggregates
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    saves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    booking_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_bookings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ratings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Segment info (optional — some snapshots are segment-specific)
    segment_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    segment_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    segment_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_prov_synth_demand_provider_period",
              "provider_id", "period_start", "period_end"),
        Index("ix_prov_synth_demand_provider_experience",
              "provider_id", "experience_id"),
    )
