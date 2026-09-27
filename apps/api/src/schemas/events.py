"""External event schemas (Phase 9).

EventResponse is the normalized, read-only shape for GET
/api/v1/context/events. Kept distinct from ExperienceSummary on purpose
— events are candidate context, never treated as catalog experiences
without an explicit approved transform (docs/AI_CONTEXT.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EventStatusLiteral = Literal["SCHEDULED", "RESCHEDULED", "CANCELLED", "POSTPONED", "UNKNOWN"]


class EventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    name: str
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: EventStatusLiteral
    venue_name: str | None = None
    venue_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    image_url: str | None = None
    purchase_url: str | None = None
    is_synthetic: bool
    fetched_at: datetime


__all__ = ["EventResponse", "EventStatusLiteral"]
