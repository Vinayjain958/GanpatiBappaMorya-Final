from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProviderMeResponse(BaseModel):
    """Full provider profile — only ever returned to the owning provider."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    description: str | None = None
    provider_type: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    verification_status: str
    city: str | None = None
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime


class ProviderUpdateRequest(BaseModel):
    """Editable business-facing fields only.

    Deliberately excludes user_id, verification_status, provenance, and
    any audit/system field — a provider cannot self-verify or reassign
    ownership (docs/AI_CONTEXT.md INV-3, docs/DECISIONS.md ADR-021).
    """

    business_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    provider_type: str | None = Field(default=None, max_length=40)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
