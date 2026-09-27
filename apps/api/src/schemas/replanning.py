"""Replanning schemas (Phase 9).

ReplanRequest carries NO traveler_id (server-derived, matching every
other Phase 8/9 request shape). `expected_version` implements the
optimistic-locking contract: a mismatch is a 409 with
ITINERARY_VERSION_CONFLICT (see src/services/replanning.py). ReplanResponse
is always a structured shape — never just text.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReplanTriggerLiteral = Literal[
    "USER_REQUESTED", "TIME_CHANGED", "BUDGET_CHANGED", "PARTY_SIZE_CHANGED",
    "WEATHER_CHANGED", "EVENT_CANCELLED", "EVENT_RESCHEDULED", "EVENT_VENUE_CHANGED",
    "AVAILABILITY_CHANGED",
]
ReplanStatusLiteral = Literal["NO_CHANGE", "REPLANNED", "REPLAN_FAILED", "REQUIRES_USER_ACTION", "CONFLICT"]


class ReplanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)
    reason: str | None = Field(default=None, max_length=500)
    # Only USER_REQUESTED-family changes may be supplied by the traveler
    # directly through this endpoint; context-driven triggers
    # (WEATHER_CHANGED etc.) originate only from ContextMonitor.
    trigger: ReplanTriggerLiteral = "USER_REQUESTED"
    new_start_time: str | None = None  # HH:MM
    new_end_time: str | None = None
    new_max_budget: float | None = Field(default=None, ge=0)
    new_party_size: int | None = Field(default=None, ge=1, le=50)


class ReplanChangeSetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_items: list[str] = Field(default_factory=list)
    removed_items: list[str] = Field(default_factory=list)
    moved_items: list[str] = Field(default_factory=list)
    unchanged_items: list[str] = Field(default_factory=list)
    affected_items: list[str] = Field(default_factory=list)


class ReplanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReplanStatusLiteral
    itinerary_id: str | None = None
    previous_version: int | None = None
    new_version: int | None = None
    trigger: str | None = None
    changes: ReplanChangeSetResponse = Field(default_factory=ReplanChangeSetResponse)
    context_summary: str = ""
    validation_issues: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    message: str | None = None
    generated_at: datetime | None = None


__all__ = [
    "ReplanChangeSetResponse",
    "ReplanRequest",
    "ReplanResponse",
    "ReplanStatusLiteral",
    "ReplanTriggerLiteral",
]
