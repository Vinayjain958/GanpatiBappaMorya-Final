from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    Index,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.availability import ExperienceAvailability
    from src.models.category import ExperienceCategory
    from src.models.embedding import ExperienceEmbedding
    from src.models.interaction import TravelerInteraction
    from src.models.location import Location
    from src.models.opening_hour import ExperienceOpeningHour
    from src.models.provider import Provider
    from src.models.review import ExperienceReview

ExperienceStatus = Enum(
    "active", "draft", "inactive", name="experience_status", native_enum=False
)
VerificationStatus = Enum(
    "unverified", "catalog_imported", "curated", "verified",
    name="experience_verification_status", native_enum=False,
)
PriceType = Enum(
    "fixed", "range", "free", "unknown", name="experience_price_type", native_enum=False
)

# ─── Phase 9: environmental/weather metadata ────────────────────────────
# Minimal, backward-compatible additions for WeatherImpactService
# (src/services/weather_impact.py). Defaulting to UNKNOWN rather than a
# guessed value — an experience imported before Phase 9 is UNKNOWN on
# every one of these fields until explicitly curated, never silently
# treated as e.g. OUTDOOR.
EnvironmentalType = Enum(
    "INDOOR", "OUTDOOR", "MIXED", "UNKNOWN", name="experience_environmental_type", native_enum=False
)
WeatherSensitivity = Enum(
    "LOW", "MEDIUM", "HIGH", "UNKNOWN", name="experience_weather_sensitivity", native_enum=False
)
WeatherPolicy = Enum(
    "NONE", "LIGHT_RAIN_OK", "WEATHER_SENSITIVE", "SEVERE_WEATHER_EXCLUDE",
    name="experience_weather_policy", native_enum=False,
)


class Experience(UUIDPrimaryKeyMixin, TimestampMixin, ProvenanceMixin, Base):
    """A discoverable local experience.

    Populated from two lineages (see data/README.md):
      1. Overture Places → normalized → enriched (is_synthetic=False, is_enriched=True)
      2. LocaLens synthetic templates (is_synthetic=True)

    Fields with a `_source`/`_estimated`/`_confidence` counterpart exist so
    the API and frontend can distinguish a verified source fact from a
    LocaLens-derived estimate. Nothing here decides feasibility or ranking
    — that is Phase 6/7.
    """

    __tablename__ = "experiences"
    __table_args__ = (
        UniqueConstraint("source_type", "source_record_id", name="uq_experience_source_record"),
        Index("ix_experiences_provider_id", "provider_id"),
        Index("ix_experiences_category_id", "category_id"),
        Index("ix_experiences_status", "status"),
    )

    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experience_categories.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    short_description: Mapped[str] = mapped_column(String(300), nullable=False)
    full_description: Mapped[str] = mapped_column(Text, nullable=False)

    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    minimum_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_type: Mapped[str] = mapped_column(PriceType, default="unknown", nullable=False)
    price_source: Mapped[str] = mapped_column(String(20), default="unavailable", nullable=False)
    price_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_price_estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    minimum_group_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_group_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(ExperienceStatus, default="active", nullable=False)
    verification_status: Mapped[str] = mapped_column(
        VerificationStatus, default="unverified", nullable=False
    )

    wheelchair_accessible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    step_free: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accessibility_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    suitability: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    opening_hours_status: Mapped[str] = mapped_column(
        String(20), default="unavailable", nullable=False
    )

    # ─── Phase 9: environmental/weather metadata ────────────────────────
    environmental_type: Mapped[str] = mapped_column(EnvironmentalType, default="UNKNOWN", nullable=False)
    weather_sensitivity: Mapped[str] = mapped_column(WeatherSensitivity, default="UNKNOWN", nullable=False)
    weather_policy: Mapped[str] = mapped_column(WeatherPolicy, default="NONE", nullable=False)

    # ─── Image resolution (Wikimedia Commons image system) ──────────────
    # image_source distinguishes how image_url was populated:
    #   "provider_upload"   -> a real business uploaded this themselves;
    #                          the enrichment script must NEVER overwrite it.
    #   "traveler_upload"    -> a traveler's own photo from the "Add a Local
    #                          Experience" flow; same precedence as
    #                          provider_upload — enrichment must NEVER overwrite it.
    #   "wikimedia_commons"  -> resolved via src/services/experience_images.py;
    #                          image_is_synthetic is always False.
    #   "category_fallback"  -> LocaLens's own generic per-category stock
    #                          image; image_is_synthetic is always True.
    #   None                -> not yet enriched.
    # image_is_place_specific distinguishes an image of the actual venue
    # (exact/geo match) from a semantic/category placeholder that merely
    # depicts the general kind of place — both can be non-synthetic
    # Wikimedia content, but only the former should be shown without a
    # "representative image" qualifier (see docs/DECISIONS.md image ADR).
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_source_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    image_license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_license_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    image_attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_is_place_specific: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    image_is_synthetic: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    image_match_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    provider: Mapped[Provider] = relationship(back_populates="experiences")
    category: Mapped[ExperienceCategory] = relationship(back_populates="experiences")
    location: Mapped[Location] = relationship(back_populates="experiences")
    opening_hours: Mapped[list[ExperienceOpeningHour]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="ExperienceOpeningHour.day_of_week",
    )
    # Phase 3 ExperienceAvailability declares its own relationship() with no
    # back_populates (see models/availability.py); this side is added in
    # Phase 6 so FeasibilityService/repositories can eager-load slots via
    # `Experience.availability_slots` without a second query pattern.
    availability_slots: Mapped[list[ExperienceAvailability]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="ExperienceAvailability.starts_at",
    )
    embedding: Mapped[ExperienceEmbedding | None] = relationship(
        back_populates="experience", cascade="all, delete-orphan", uselist=False
    )
    interactions: Mapped[list[TravelerInteraction]] = relationship(
        back_populates="experience", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[ExperienceReview]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="ExperienceReview.reviewed_at.desc()",
    )
