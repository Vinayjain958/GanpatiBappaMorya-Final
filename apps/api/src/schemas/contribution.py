"""Schemas for the traveler direct-publish contribution endpoint.

`traveler_id` never appears here — it is always derived from the
authenticated session on the server, the same convention
`schemas/experience_write.py` documents for `provider_id`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

_ALLOWED_URL_SCHEMES = ("http://", "https://")


class ContributionCreateForm(BaseModel):
    """Parsed from multipart/form-data fields (the image travels as a
    separate `UploadFile`, not a field on this model) — see
    api/v1/contributions.py."""

    name: str = Field(min_length=2, max_length=200)
    category_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    place_name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    contact_phone: str = Field(min_length=5, max_length=40)
    description: str | None = Field(default=None, max_length=4000)
    website: str | None = Field(default=None, max_length=500)
    override_duplicate_check: bool = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Please enter the experience name.")
        if len(set(normalized.replace(" ", ""))) <= 1 and len(normalized) > 3:
            # e.g. "aaaaaaaa" — obvious junk, not a real place name.
            raise ValueError("Please enter a real experience name.")
        return normalized

    @field_validator("website")
    @classmethod
    def _validate_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        candidate = value.strip()
        if not candidate.lower().startswith(_ALLOWED_URL_SCHEMES):
            raise ValueError("Website must start with http:// or https://")
        return candidate

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ContributionSummary(BaseModel):
    id: str
    status: str


class ContributionPublishResponse(BaseModel):
    """Returned on success — `experience` reuses the same
    `ExperienceDetail` shape every other catalog read returns, since this
    is a real Experience row, not a separate model."""

    experience: dict[str, Any]
    contribution: ContributionSummary


class DuplicateFoundResponse(BaseModel):
    """Returned instead of publishing when duplicate detection finds a
    match — a decision point for the client, not a hard error.
    `POSSIBLE_DUPLICATE` can be bypassed by resubmitting with
    `override_duplicate_check=true`; `DUPLICATE_EXPERIENCE` cannot."""

    detail: str
    existing_experience_id: str
    reason: str
