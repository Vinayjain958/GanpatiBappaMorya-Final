"""Feasibility schemas (Phase 6).

TravelerConstraints is the single validated input shape for
FeasibilityService — never raw dicts. A constraint field left as None
means "traveler did not ask for this" (not applicable, never blocking).
Explicit invalid values (negative budget, end<start, etc.) are rejected
at the Pydantic boundary, never silently coerced.

FeasibilityVerdict/FeasibilityReason are the tri-state output shape.
UNKNOWN can never be upgraded to FEASIBLE by any caller — see
FeasibilityService.evaluate in src/services/feasibility.py.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.feasibility_reasons import FeasibilityReasonCode

FeasibilityStatus = Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN"]


class CommittedTimeBlock(BaseModel):
    """An existing committed time block the candidate experience (plus its
    travel time) must fit around. Phase 6 accepts these as plain input —
    no Itinerary/ItineraryItem persistence model (that is Phase 8)."""

    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _check_order(self) -> CommittedTimeBlock:
        if self.end <= self.start:
            raise ValueError("CommittedTimeBlock.end must be after start")
        return self


class TravelerConstraints(BaseModel):
    """Validated traveler-supplied feasibility constraints. Every field is
    optional — a missing field means the traveler did not request that
    constraint, so the corresponding check is skipped (not applicable),
    never treated as failing or as passing."""

    model_config = ConfigDict(extra="forbid")

    # Budget — INR only (no currency conversion in Phase 6).
    currency: str = Field(default="INR", min_length=3, max_length=3)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)

    # Time context.
    available_date: date | None = None
    available_start: time | None = None
    available_end: time | None = None
    available_duration_minutes: int | None = Field(default=None, gt=0)
    timezone: str | None = None

    # Travel / location.
    origin_lat: float | None = Field(default=None, ge=-90, le=90)
    origin_lng: float | None = Field(default=None, ge=-180, le=180)
    travel_mode: Literal["driving", "walking", "cycling"] | None = None
    max_distance_km: float | None = Field(default=None, gt=0)
    max_travel_time_minutes: float | None = Field(default=None, gt=0)

    # Group / accessibility.
    party_size: int | None = Field(default=None, ge=1, le=200)
    accessibility_requirements: list[Literal["wheelchair_accessible", "step_free"]] = Field(
        default_factory=list
    )

    # Itinerary conflicts — plain interval input, not a persisted model.
    existing_commitments: list[CommittedTimeBlock] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_ranges(self) -> TravelerConstraints:
        if self.budget_min is not None and self.budget_max is not None and self.budget_max < self.budget_min:
            raise ValueError("budget_max must be >= budget_min")
        if (
            self.available_start is not None
            and self.available_end is not None
            and self.available_end <= self.available_start
        ):
            raise ValueError("available_end must be after available_start")
        if (self.origin_lat is None) != (self.origin_lng is None):
            raise ValueError("origin_lat and origin_lng must both be provided or both omitted")
        return self


class FeasibilityEvidence(BaseModel):
    """Structured evidence backing a reason — real stored/computed values
    only, never fabricated. Extra fields are allowed since evidence shape
    varies per check (e.g. distance_km vs travel_time_minutes)."""

    model_config = ConfigDict(extra="allow")


class FeasibilityReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: FeasibilityReasonCode
    constraint: str
    message: str
    blocking: bool
    evidence: dict[str, object] = Field(default_factory=dict)


class FeasibilityVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    status: FeasibilityStatus
    reasons: list[FeasibilityReason] = Field(default_factory=list)
    checked_at: datetime
    evidence: dict[str, object] = Field(default_factory=dict)


class FeasibilityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    constraints: TravelerConstraints = Field(default_factory=TravelerConstraints)


__all__ = [
    "CommittedTimeBlock",
    "FeasibilityCheckRequest",
    "FeasibilityEvidence",
    "FeasibilityReason",
    "FeasibilityStatus",
    "FeasibilityVerdict",
    "TravelerConstraints",
]
