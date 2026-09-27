from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.traveler import Traveler

class TravelerPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit, stable user preferences edited directly by the traveler."""

    __tablename__ = "traveler_preferences"

    traveler_id: Mapped[str] = mapped_column(String(36), ForeignKey("travelers.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferred_category_slugs: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    budget_sensitivity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_max_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    accessibility_requirements: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    traveler: Mapped[Traveler] = relationship(back_populates="preference")
