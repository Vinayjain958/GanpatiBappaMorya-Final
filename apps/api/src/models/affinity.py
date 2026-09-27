from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Index, UniqueConstraint

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.traveler import Traveler

class TravelerAffinity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Learned long-term behavioral affinity updated from interaction events."""

    __tablename__ = "traveler_affinities"

    traveler_id: Mapped[str] = mapped_column(String(36), ForeignKey("travelers.id", ondelete="CASCADE"), nullable=False, index=True)
    dimension_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    traveler: Mapped[Traveler] = relationship(back_populates="affinities")

    __table_args__ = (
        UniqueConstraint("traveler_id", "dimension_type", "dimension_key", name="uq_traveler_affinity_dim"),
        Index("ix_traveler_affinities_traveler_id_dim_type", "traveler_id", "dimension_type"),
    )
