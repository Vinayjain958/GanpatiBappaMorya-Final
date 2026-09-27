from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UpdatePreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_category_slugs: list[str] | None = None
    budget_sensitivity: str | None = None
    preferred_duration_minutes: int | None = None
    preferred_max_distance_km: float | None = None
    accessibility_requirements: list[str] | None = None

class TravelerPreferenceResponse(UpdatePreferenceRequest):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    traveler_id: str

__all__ = [
    "UpdatePreferenceRequest",
    "TravelerPreferenceResponse",
]
