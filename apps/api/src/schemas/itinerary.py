"""Itinerary schemas (Phase 8).

ComposeItineraryRequest carries NO traveler_id field — it is always
server-derived from the authenticated user (require_traveler), matching
the Phase 7 /recommendations contract (see src/api/v1/itineraries.py).
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ItineraryStatusLiteral = Literal["DRAFT", "VALIDATED", "BOOKING_REQUESTED", "COMPLETED", "CANCELLED"]
ItinerarySourceLiteral = Literal["COMPOSER", "MANUAL"]
PaceLiteral = Literal["relaxed", "balanced", "packed"]


class ComposeItineraryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    # Optional canonical catalog ids selected in the Trip discovery UI.
    # Existing callers may omit this field and continue using query-based
    # retrieval exactly as before.
    experience_ids: list[str] = Field(default_factory=list, max_length=20)
    custom_activities: list[CustomActivityRequest] = Field(default_factory=list, max_length=20)
    interests: list[str] = Field(default_factory=list)
    category_slugs: list[str] = Field(default_factory=list)
    itinerary_date: date
    start_time: time
    end_time: time
    max_experiences: int | None = Field(default=None, ge=1, le=20)
    max_budget: float | None = Field(default=None, ge=0)
    pace: PaceLiteral = "balanced"
    origin_lat: float | None = Field(default=None, ge=-90, le=90)
    origin_lng: float | None = Field(default=None, ge=-180, le=180)
    travel_mode: Literal["driving", "walking", "cycling"] = "driving"
    party_size: int | None = Field(default=None, ge=1, le=50)
    accessibility_requirements: list[Literal["wheelchair_accessible", "step_free"]] = Field(
        default_factory=list
    )
    city: str | None = None
    locality: str | None = None

    @model_validator(mode="after")
    def _check_window(self) -> ComposeItineraryRequest:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if len(set(self.experience_ids)) != len(self.experience_ids):
            raise ValueError("experience_ids must not contain duplicates")
        if self.max_experiences is not None and len(self.experience_ids) > self.max_experiences:
            raise ValueError("experience_ids cannot exceed max_experiences")
        for activity in self.custom_activities:
            if activity.start_time < self.start_time or activity.start_time >= self.end_time:
                raise ValueError("custom activity start_time must be inside the itinerary window")
            if (
                activity.duration_minutes
                and activity.start_time.hour * 60 + activity.start_time.minute + activity.duration_minutes
                > self.end_time.hour * 60 + self.end_time.minute
            ):
                raise ValueError("custom activity must end before the itinerary window ends")
        return self


class CustomActivityRequest(BaseModel):
    """A personal note, place, or activity; it never creates a catalog row."""

    model_config = ConfigDict(extra="forbid")

    client_id: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["place", "activity", "note"] = "activity"
    note: str | None = Field(default=None, max_length=2000)
    location_text: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_time: time
    duration_minutes: int = Field(default=30, ge=0, le=720)
    estimated_cost: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_coordinates(self) -> CustomActivityRequest:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or omitted")
        if self.kind == "note" and self.estimated_cost is None:
            self.estimated_cost = 0
        return self


class ItineraryCustomActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence_order: int
    title: str
    kind: Literal["place", "activity", "note"]
    note: str | None = None
    location_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    planned_start: datetime
    planned_end: datetime
    duration_minutes: int
    estimated_cost: float | None = None


class PreviewItineraryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str | None = None
    client_id: str | None = None
    title: str
    kind: Literal["place", "activity", "note"] = "place"
    planned_start: datetime
    planned_end: datetime
    duration_minutes: int
    travel_from_previous_minutes: float | None = None
    travel_from_previous_distance_km: float | None = None
    travel_time_source: Literal["osrm", "haversine_estimate"] | None = None
    estimated_cost: float | None = None


class ItineraryPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    experience_ids: list[str]
    items: list[PreviewItineraryItem] = Field(default_factory=list)
    visit_minutes: int = 0
    travel_minutes: float | None = None
    total_minutes: float | None = None
    estimated_total_cost: float | None = None
    has_estimated_cost: bool = False
    travel_time_source: Literal["osrm", "haversine_estimate"] | None = None
    issues: list[CompositionValidationIssue] = Field(default_factory=list)
    demo_schedule_used: bool = False


class PreviewIdeasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: ComposeItineraryRequest
    plans: list[list[str]] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _check_plans(self) -> PreviewIdeasRequest:
        if not self.plans:
            raise ValueError("at least one plan is required")
        if any(not ids or len(ids) > 20 or len(set(ids)) != len(ids) for ids in self.plans):
            raise ValueError("each plan must contain 1-20 unique experience ids")
        if self.base.custom_activities:
            raise ValueError("batch suggestions cannot include personal activities")
        return self


class ItineraryOpeningHour(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_of_week: int
    open_time: str | None = None
    close_time: str | None = None
    is_closed: bool
    is_synthetic: bool = False


class NearbyOpenAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    title: str
    category_name: str
    locality: str | None = None
    city: str
    distance_km: float
    opening_hours_for_visit: list[ItineraryOpeningHour] = Field(default_factory=list)
    is_synthetic: bool = False


class ItineraryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experience_id: str
    sequence_order: int
    planned_start: datetime
    planned_end: datetime
    duration_minutes: int
    travel_from_previous_minutes: float | None = None
    travel_from_previous_distance_km: float | None = None
    travel_mode: str | None = None
    buffer_before_minutes: int
    buffer_after_minutes: int
    estimated_cost: float | None = None
    source_rank_position: int | None = None
    source_ranking_score: float | None = None
    narrative_text: str | None = None
    is_locked: bool = False
    item_state: str = "ACTIVE"

    # Denormalized display facts (never authoritative pricing/hours source
    # — populated from the canonical Experience at response-build time).
    title: str | None = None
    short_description: str | None = None
    category_name: str | None = None
    location_place_name: str | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    opening_hours_status_at_visit: Literal["open", "closed", "unknown"] = "unknown"
    opening_hours_for_visit: list[ItineraryOpeningHour] = Field(default_factory=list)
    nearby_open_alternatives: list[NearbyOpenAlternative] = Field(default_factory=list)
    availability_data_is_synthetic: bool = False


class ItineraryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    traveler_id: str
    title: str
    itinerary_date: date
    start_time: time
    end_time: time
    status: ItineraryStatusLiteral
    source: ItinerarySourceLiteral
    total_duration_minutes: int | None = None
    total_travel_minutes: float | None = None
    estimated_total_cost: float | None = None
    max_budget: float | None = None
    currency: str
    narrative_title: str | None = None
    narrative_summary: str | None = None
    narrative_closing_message: str | None = None
    ranking_model_version: str | None = None
    narrative_model_version: str | None = None
    generated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ItineraryItemResponse] = Field(default_factory=list)
    custom_activities: list[ItineraryCustomActivityResponse] = Field(default_factory=list)

    # ─── Phase 9: versioning/replanning state ───────────────────────────
    version: int = 1
    replanning_status: str = "STABLE"
    context_last_updated_at: datetime | None = None


class ItineraryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ItineraryResponse]
    total: int


class CompositionValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    constraint: str
    message: str
    evidence: dict[str, object] = Field(default_factory=dict)


class CompositionValidationResponse(BaseModel):
    """Returned instead of an ItineraryResponse when composition could not
    produce a valid plan — never a forced/partial itinerary."""

    model_config = ConfigDict(extra="forbid")

    valid: bool = False
    reason_code: str
    message: str
    issues: list[CompositionValidationIssue] = Field(default_factory=list)
    candidate_count: int = 0
    feasible_count: int = 0


class AddItineraryItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    planned_start: datetime | None = None
    travel_mode: Literal["driving", "walking", "cycling"] = "driving"


# Resolve references to additive request/issue shapes declared later in this
# module once their full schemas are available.
ComposeItineraryRequest.model_rebuild()
ItineraryPreviewResponse.model_rebuild()


__all__ = [
    "AddItineraryItemRequest",
    "CustomActivityRequest",
    "ComposeItineraryRequest",
    "CompositionValidationIssue",
    "CompositionValidationResponse",
    "ItineraryItemResponse",
    "ItineraryCustomActivityResponse",
    "ItineraryListResponse",
    "ItineraryPreviewResponse",
    "ItineraryResponse",
    "PreviewIdeasRequest",
    "PreviewItineraryItem",
]
