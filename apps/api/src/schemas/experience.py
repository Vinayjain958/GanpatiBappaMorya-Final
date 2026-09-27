"""Pydantic response schemas for the Experience read API.

These are the only shapes the frontend ever sees — SQLAlchemy models are
never returned directly from a route. Nothing here exposes secrets or
internal-only fields (see docs/AI_CONTEXT.md INV-3/INV-5).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    icon: str | None = None


class LocationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    latitude: float
    longitude: float
    place_name: str | None = None
    address: str | None = None
    locality: str | None = None
    city: str
    state: str | None = None
    country: str | None = None


class ProviderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    provider_type: str | None = None
    verification_status: str
    is_synthetic: bool


class OpeningHourWindow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_of_week: int
    open_time: str | None = None
    close_time: str | None = None
    is_closed: bool
    is_synthetic: bool = False


class AvailabilitySlotSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    available_slots: int | None = None
    status: str
    is_synthetic: bool = True


class ExperienceReviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rating_value: int
    title: str
    body: str
    author_display_name: str
    reviewed_at: datetime
    is_synthetic: bool = True


class RatingSummary(BaseModel):
    average_rating: float | None = None
    review_count: int = 0
    rating_distribution: dict[int, int] = {}
    is_synthetic: bool = True


class ExperienceImage(BaseModel):
    """Normalized image metadata — see src/services/experience_images.py
    and src/models/experience.py's image_* columns. `image_url` is None
    when no suitable image has been resolved yet (never a fabricated
    placeholder); the frontend falls back to its own generic category
    art in that case, clearly distinct from a real venue photo."""

    model_config = ConfigDict(from_attributes=True)

    url: str | None = None
    thumbnail_url: str | None = None
    source: str | None = None
    source_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    author: str | None = None
    attribution_text: str | None = None
    is_place_specific: bool | None = None
    is_synthetic: bool | None = None
    match_method: str | None = None


class ExperienceSummary(BaseModel):
    """Compact shape used in list responses (matches the Discover grid)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    short_description: str
    category: CategorySummary
    location: LocationSummary
    provider: ProviderSummary
    currency: str
    price: float | None = None
    minimum_price: float | None = None
    maximum_price: float | None = None
    price_type: str
    is_price_estimated: bool
    duration_minutes: int | None = None
    duration_is_estimated: bool
    rating: float | None = None
    rating_source: str | None = None
    review_count: int | None = None
    status: str
    verification_status: str
    is_synthetic: bool
    is_enriched: bool
    image: ExperienceImage | None = None

    @model_validator(mode="before")
    @classmethod
    def _build_image_from_flat_columns(cls, data: Any) -> Any:
        """The ORM stores image_* as flat columns (src/models/experience.py)
        but the API exposes them as a nested `image` object — assembled
        here rather than duplicating the flat/nested shape in the model."""
        if isinstance(data, dict):
            return data
        image = None
        if getattr(data, "image_url", None) is not None:
            image = ExperienceImage(
                url=data.image_url,
                thumbnail_url=data.image_thumbnail_url,
                source=data.image_source,
                source_url=data.image_source_url,
                license=data.image_license,
                license_url=data.image_license_url,
                author=data.image_author,
                attribution_text=data.image_attribution_text,
                is_place_specific=data.image_is_place_specific,
                is_synthetic=data.image_is_synthetic,
                match_method=data.image_match_method,
            )
        values = {
            field: getattr(data, field)
            for field in cls.model_fields
            if field != "image"
            and field not in ("reviews", "rating_summary")
            and hasattr(data, field)
        }
        values["image"] = image
        return values

    # Location-aware discovery fields (Phase 4). distance_km is a
    # straight-line Haversine distance — only populated when the request
    # included lat/lng. travel_time_minutes is only populated for the
    # current result page when travel-time enrichment succeeded;
    # travel_time_source distinguishes a real OSRM route from a labelled
    # straight-line estimate — never presented as exact routing when it
    # isn't (docs/DECISIONS.md ADR-023).
    distance_km: float | None = None
    travel_time_minutes: float | None = None
    travel_time_source: str | None = None


class ExperienceDetail(ExperienceSummary):
    """Full shape used for the experience detail page."""

    full_description: str
    minimum_group_size: int | None = None
    maximum_group_size: int | None = None
    capacity: int | None = None
    wheelchair_accessible: bool | None = None
    step_free: bool | None = None
    accessibility_notes: str | None = None
    suitability: list[str] | None = None
    tags: list[str] | None = None
    opening_hours_status: str
    opening_hours: list[OpeningHourWindow] = []
    availability_slots: list[AvailabilitySlotSummary] = []
    rating_summary: RatingSummary | None = None
    reviews: list[ExperienceReviewSummary] = []
    source_type: str
    source_name: str | None = None
    source_license: str | None = None
    attribution_required: bool
    attribution_text: str | None = None
    created_at: datetime
    updated_at: datetime


class ExperienceListResponse(BaseModel):
    items: list[ExperienceSummary]
    total: int
    limit: int
    offset: int


class ExperienceReviewListResponse(BaseModel):
    items: list[ExperienceReviewSummary]
    total: int
    limit: int
    offset: int
