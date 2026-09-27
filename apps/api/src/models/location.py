from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience


class Location(UUIDPrimaryKeyMixin, TimestampMixin, ProvenanceMixin, Base):
    """Portable lat/lng location record.

    Deliberately free of PostGIS/spatial extensions and SQLite-only
    features (docs/DECISIONS.md ADR-005/ADR-006) — radius/routing queries
    are computed in Python or added properly in Phase 4.
    """

    __tablename__ = "locations"

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    place_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Mumbai")
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, default="India")
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(60), nullable=True, default="Asia/Kolkata")

    experiences: Mapped[list[Experience]] = relationship(back_populates="location")
