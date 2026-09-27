"""Public, aggregated response contracts for social context.

These schemas intentionally have no fields for post text, handles, DIDs,
post identifiers, or source URLs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.adapters.social_signals import SocialSeverity, SocialTopic


class SocialSignalClusterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    topic: SocialTopic
    location_name: str
    location_precision: Literal["area"] = "area"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    signal_count: int = Field(ge=1)
    independent_source_count: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    severity: SocialSeverity
    trend: Literal["rising", "steady", "falling", "insufficient_data"]
    newest_signal_at: datetime
    source_platforms: list[Literal["bluesky"]]
    confidence_note: str = "Heuristic context estimate, not a verified fact."


class SocialSignalsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["AVAILABLE", "NO_SIGNALS", "UNAVAILABLE", "RATE_LIMITED", "STALE"]
    queried_location: str | None = None
    radius_km: float = Field(ge=1, le=50)
    generated_at: datetime
    clusters: list[SocialSignalClusterResponse]
    message: str
