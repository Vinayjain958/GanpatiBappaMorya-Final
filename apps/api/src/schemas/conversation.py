"""Conversational AI schemas (Phase 5).

TravelerContext is the single structured-intent shape shared by both the
text and voice paths — see docs/DECISIONS.md ADR-034. It is intentionally
scoped to what Phase 5 needs (understanding + retrieval); it is not an
itinerary/feasibility model (those are Phase 6/8).

Gemini never supplies coordinates directly (location_text is free text
only) and category_slugs are always re-validated against the canonical
taxonomy before use — see src/services/ai_tools.py.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.digital_twin import WhatIfScenario
from src.schemas.experience import ExperienceSummary
from src.schemas.feasibility import CommittedTimeBlock


class TravelerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_query: str
    interests: list[str] = Field(default_factory=list)
    category_slugs: list[str] = Field(default_factory=list)
    location_text: str | None = None
    budget: Literal["any", "low", "mid", "high"] | None = None
    duration: Literal["any", "short", "medium", "long"] | None = None
    party_size: int | None = Field(default=None, ge=1, le=50)
    time_context: str | None = None
    notes: str | None = None

    # ─── Phase 6 extension: optional, nullable feasibility-oriented fields.
    # Additive only — no existing field above was changed or removed, so
    # every Phase 5 caller/test keeps working unmodified. Gemini never
    # supplies origin_lat/origin_lng directly in practice (the frontend/
    # traveler device does); these exist so a fully-specified
    # TravelerContext can be converted into TravelerConstraints for the
    # feasibility pipeline (see src/services/ai_tools.py).
    currency: str | None = None
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    available_date: date | None = None
    available_start: time | None = None
    available_end: time | None = None
    # ge=0 rather than gt=0: Gemini's structured-output schema converter
    # (response_schema=TravelerContext is sent directly to the API, unlike
    # the tool-argument schemas below which Gemini never parses as JSON
    # Schema) rejects Pydantic's `exclusiveMinimum` keyword as an
    # unsupported property. Downstream feasibility validation already
    # treats a supplied 0 the same as "not meaningfully constrained".
    available_duration_minutes: int | None = Field(default=None, ge=0)
    timezone: str | None = None
    origin_lat: float | None = Field(default=None, ge=-90, le=90)
    origin_lng: float | None = Field(default=None, ge=-180, le=180)
    travel_mode: Literal["driving", "walking", "cycling"] | None = None
    max_distance_km: float | None = Field(default=None, ge=0)
    max_travel_time_minutes: float | None = Field(default=None, ge=0)
    accessibility_requirements: list[Literal["wheelchair_accessible", "step_free"]] = Field(
        default_factory=list
    )
    existing_commitments: list[CommittedTimeBlock] = Field(default_factory=list)


class SearchExperiencesArgs(BaseModel):
    """Tool-call argument schema. Validated before ever reaching
    ExperienceDiscoveryService — raw model tool arguments are never
    trusted directly."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    category_slug: str | None = None
    city: str | None = None
    locality: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    min_duration_minutes: int | None = Field(default=None, ge=0)
    max_duration_minutes: int | None = Field(default=None, ge=0)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=None, gt=0)
    sort: Literal["relevance", "distance", "price", "duration", "newest"] = "relevance"
    limit: int = Field(default=5, ge=1, le=10)


class SearchExperiencesResult(BaseModel):
    items: list[ExperienceSummary]
    total: int
    truncated: bool


class CheckFeasibilityArgs(BaseModel):
    """Tool-call argument schema for check_feasibility. Gemini supplies
    only an experience_id and constraint context — it can never invent
    price/hours/capacity/availability values; those are always loaded
    from the database by the tool implementation (src/services/ai_tools.py)."""

    model_config = ConfigDict(extra="forbid")

    experience_id: str
    budget_max: float | None = Field(default=None, ge=0)
    available_duration_minutes: int | None = Field(default=None, gt=0)
    party_size: int | None = Field(default=None, ge=1, le=200)
    max_travel_time_minutes: float | None = Field(default=None, gt=0)
    max_distance_km: float | None = Field(default=None, gt=0)
    origin_lat: float | None = Field(default=None, ge=-90, le=90)
    origin_lng: float | None = Field(default=None, ge=-180, le=180)
    accessibility_requirements: list[Literal["wheelchair_accessible", "step_free"]] = Field(
        default_factory=list
    )


class ComposeExperienceArgs(BaseModel):
    """Tool-call argument schema for compose_experience (Phase 8). Never
    accepts traveler_id — it is always server-derived. experience_ids are
    only a *hint*; the tool implementation verifies every id against the
    conversation's authorized candidate context
    (ConversationSession.last_search_candidates) rather than trusting raw
    ids Gemini supplies (see src/services/ai_tools.py)."""

    model_config = ConfigDict(extra="forbid")

    experience_ids: list[str] = Field(default_factory=list)
    itinerary_date: date
    start_time: time
    end_time: time
    max_experiences: int | None = Field(default=None, ge=1, le=20)
    max_budget: float | None = Field(default=None, ge=0)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    must_include_ids: list[str] = Field(default_factory=list)
    exclude_ids: list[str] = Field(default_factory=list)


class ReplanExperienceArgs(BaseModel):
    """Tool-call argument schema for replan_experience (Phase 9). Gemini
    may supply a requested change, an affected experience id (hint only,
    always revalidated server-side), traveler intent text, and
    time/budget constraints — NEVER traveler_id, provider authorization,
    the final itinerary state, or a booking confirmation. The tool
    implementation only ever forwards these as an intent/reason string
    and constraint hints into ReplanningService — it never lets Gemini
    directly edit the itinerary (src/services/ai_tools.py)."""

    model_config = ConfigDict(extra="forbid")

    itinerary_id: str
    affected_experience_id: str | None = None
    requested_change: str = Field(min_length=1, max_length=500)
    new_start_time: time | None = None
    new_end_time: time | None = None
    new_max_budget: float | None = Field(default=None, ge=0)
    new_party_size: int | None = Field(default=None, ge=1, le=50)


class SimulateWhatIfArgs(BaseModel):
    """Preview-only AI tool arguments; itinerary ownership is server-derived."""

    model_config = ConfigDict(extra="forbid")

    itinerary_id: str = Field(min_length=1, max_length=36)
    scenario: WhatIfScenario = Field(default_factory=WhatIfScenario)


class ToolCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    args: dict[str, object] = Field(default_factory=dict)


class ConversationTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)


class ConversationTurnResponse(BaseModel):
    message_id: str
    assistant_text: str
    traveler_context: TravelerContext
    tool_results: SearchExperiencesResult | None = None


class ConversationCreateResponse(BaseModel):
    id: str
    created_at: datetime


class ConversationMessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    id: str
    created_at: datetime
    messages: list[ConversationMessagePublic]
    latest_traveler_context: TravelerContext | None = None


class LiveTokenResponse(BaseModel):
    token: str
    expire_time: datetime
    new_session_expire_time: datetime
    model: str
