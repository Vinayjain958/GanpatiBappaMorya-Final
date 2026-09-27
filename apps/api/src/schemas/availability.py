from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AvailabilityCreateRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(ge=1)
    available_slots: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_window(self) -> AvailabilityCreateRequest:
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at")
        return self


class AvailabilityUpdateRequest(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=1)
    available_slots: int | None = Field(default=None, ge=0)
    status: Literal["active", "cancelled", "inactive"] | None = None

    @model_validator(mode="after")
    def validate_window(self) -> AvailabilityUpdateRequest:
        if self.starts_at is not None and self.ends_at is not None and self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at")
        return self


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experience_id: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    available_slots: int | None = None
    status: str
