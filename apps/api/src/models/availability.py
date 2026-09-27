from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience

AvailabilityStatus = Enum("active", "cancelled", "inactive", name="availability_status", native_enum=False)


class ExperienceAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A specific bookable time window for an experience.

    Distinct from ExperienceOpeningHour (recurring weekly hours, e.g.
    "usually open Mon 10:00-18:00"): this is a concrete instance, e.g.
    "available 2026-10-10 14:00-15:30, capacity 8". Booking/reservation
    logic against this table is Phase 8 — Phase 3 only manages the slots
    themselves. Datetimes are stored timezone-aware (UTC) per
    docs/DECISIONS.md; no SQLite-specific datetime handling.
    """

    __tablename__ = "experience_availability"

    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    available_slots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(AvailabilityStatus, default="active", nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    experience: Mapped[Experience] = relationship(back_populates="availability_slots")
