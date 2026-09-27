"""Write schemas for provider-owned experiences.

`provider_id` is deliberately absent from every schema here — ownership
is always derived from the authenticated provider on the server
(docs/DECISIONS.md ADR-021), never accepted from the request body.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OpeningHourInput(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    open_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    close_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    is_closed: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> OpeningHourInput:
        if self.is_closed:
            return self
        if not self.open_time or not self.close_time:
            raise ValueError("open_time and close_time are required unless is_closed is true")
        if self.open_time >= self.close_time:
            raise ValueError("open_time must be before close_time")
        return self


class LocationInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    place_name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    locality: str | None = Field(default=None, max_length=120)
    city: str = Field(default="Mumbai", max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str = Field(default="India", max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)


class ExperienceCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    short_description: str = Field(min_length=10, max_length=300)
    full_description: str = Field(min_length=10, max_length=5000)
    category_id: str

    location: LocationInput

    currency: str = Field(default="INR", min_length=3, max_length=3)
    price: float | None = Field(default=None, ge=0)
    minimum_price: float | None = Field(default=None, ge=0)
    maximum_price: float | None = Field(default=None, ge=0)
    price_type: Literal["fixed", "range", "free", "unknown"] = "fixed"

    duration_minutes: int | None = Field(default=None, gt=0)
    minimum_group_size: int | None = Field(default=None, ge=1)
    maximum_group_size: int | None = Field(default=None, ge=1)
    capacity: int | None = Field(default=None, ge=1)

    wheelchair_accessible: bool | None = None
    step_free: bool | None = None
    accessibility_notes: str | None = Field(default=None, max_length=1000)

    suitability: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    status: Literal["active", "draft", "inactive"] = "draft"
    opening_hours: list[OpeningHourInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self) -> ExperienceCreateRequest:
        if (
            self.minimum_group_size is not None
            and self.maximum_group_size is not None
            and self.maximum_group_size < self.minimum_group_size
        ):
            raise ValueError("maximum_group_size must be >= minimum_group_size")
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and self.maximum_price < self.minimum_price
        ):
            raise ValueError("maximum_price must be >= minimum_price")
        return self


class ExperienceUpdateRequest(BaseModel):
    """All fields optional — only supplied fields are updated.

    Same field surface as create, minus location (location edits are out
    of scope for Phase 3 to avoid re-geocoding concerns) and minus
    anything provenance/ownership related.
    """

    title: str | None = Field(default=None, min_length=3, max_length=200)
    short_description: str | None = Field(default=None, min_length=10, max_length=300)
    full_description: str | None = Field(default=None, min_length=10, max_length=5000)
    category_id: str | None = None

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price: float | None = Field(default=None, ge=0)
    minimum_price: float | None = Field(default=None, ge=0)
    maximum_price: float | None = Field(default=None, ge=0)
    price_type: Literal["fixed", "range", "free", "unknown"] | None = None

    duration_minutes: int | None = Field(default=None, gt=0)
    minimum_group_size: int | None = Field(default=None, ge=1)
    maximum_group_size: int | None = Field(default=None, ge=1)
    capacity: int | None = Field(default=None, ge=1)

    wheelchair_accessible: bool | None = None
    step_free: bool | None = None
    accessibility_notes: str | None = Field(default=None, max_length=1000)

    suitability: list[str] | None = None
    tags: list[str] | None = None

    status: Literal["active", "draft", "inactive"] | None = None
    opening_hours: list[OpeningHourInput] | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> ExperienceUpdateRequest:
        if (
            self.minimum_group_size is not None
            and self.maximum_group_size is not None
            and self.maximum_group_size < self.minimum_group_size
        ):
            raise ValueError("maximum_group_size must be >= minimum_group_size")
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and self.maximum_price < self.minimum_price
        ):
            raise ValueError("maximum_price must be >= minimum_price")
        return self
