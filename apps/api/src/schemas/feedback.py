from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InteractionEventType = Literal[
    "IMPRESSION", "VIEW", "SAVE", "UNSAVE", "COMPLETE", "SKIP", "RATING"
]

class RecordInteractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    event_type: InteractionEventType
    rating: float | None = Field(default=None, ge=1, le=5)
    client_event_id: str = Field(..., max_length=100)
    rank_position: int | None = None
    recommendation_session_id: str | None = None
    occurred_at: datetime | None = None
    source: str | None = None

    @model_validator(mode="after")
    def validate_rating(self) -> RecordInteractionRequest:
        if self.event_type == "RATING" and self.rating is None:
            raise ValueError("rating is required for RATING event type")
        if self.event_type != "RATING" and self.rating is not None:
            raise ValueError("rating must be null for non-RATING event type")
        return self

class RecordInteractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_id: str
    created: bool
    idempotent: bool

class TravelerAffinitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension_type: str
    dimension_key: str
    score: float
    confidence: float
    interaction_count: int

class AffinityProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    traveler_id: str
    affinities: list[TravelerAffinitySummary]
    personalized_since: datetime | None = None

__all__ = [
    "InteractionEventType",
    "RecordInteractionRequest",
    "RecordInteractionResponse",
    "TravelerAffinitySummary",
    "AffinityProfileResponse",
]
