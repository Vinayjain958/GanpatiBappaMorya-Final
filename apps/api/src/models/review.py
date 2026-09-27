from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience


class ExperienceReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An individual traveler review and rating for an experience.

    Each record captures an individual 1-5 star rating and review narrative.
    The overall Experience rating and review count are strictly derived from
    these records. Full provenance is tracked to clearly separate synthetic
    demo reviews from verified customer reviews.
    """

    __tablename__ = "experience_reviews"
    __table_args__ = (
        UniqueConstraint(
            "experience_id",
            "generation_version",
            "synthetic_sequence",
            name="uq_experience_review_synthetic_seq",
        ),
        Index("ix_experience_reviews_exp_reviewed", "experience_id", "reviewed_at"),
    )

    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating_value: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 5
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # reviewed_at is the historical or semantic date of the review event,
    # distinct from created_at (TimestampMixin) which tracks DB row insertion.
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Provenance fields (docs/DECISIONS.md ADR-015)
    source_type: Mapped[str] = mapped_column(
        String(40), default="synthetic_enrichment", nullable=False
    )
    source_name: Mapped[str] = mapped_column(
        String(80), default="LocaLens synthetic review generator", nullable=False
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enriched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generation_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)
    synthetic_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    experience: Mapped[Experience] = relationship(back_populates="reviews")
