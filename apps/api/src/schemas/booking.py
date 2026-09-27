"""Booking request schemas (Phase 8).

REQUESTED intent only — no payment fields exist anywhere in this module.
BookingRequestResponse.status is never "CONFIRMED"; the frontend/UI copy
must never render ACCEPTED as "Confirmed" either (docs/DECISIONS.md
ADR-046).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BookingStatusLiteral = Literal["REQUESTED", "ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED"]


class BookingRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    itinerary_item_id: str
    party_size: int = Field(default=1, ge=1, le=200)
    traveler_note: str | None = Field(default=None, max_length=1000)


class BookingRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    traveler_id: str
    itinerary_id: str
    itinerary_item_id: str
    experience_id: str
    provider_id: str
    requested_start: datetime
    requested_end: datetime
    party_size: int
    traveler_note: str | None = None
    status: BookingStatusLiteral
    requested_at: datetime
    responded_at: datetime | None = None
    provider_note: str | None = None
    created_at: datetime
    updated_at: datetime

    # Display-only facts, never a payment/confirmation claim.
    experience_title: str | None = None


class BookingRequestListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BookingRequestResponse]
    total: int


class BookingStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ACCEPTED", "DECLINED"]
    provider_note: str | None = Field(default=None, max_length=1000)


__all__ = [
    "BookingRequestCreate",
    "BookingRequestListResponse",
    "BookingRequestResponse",
    "BookingStatusUpdate",
]
