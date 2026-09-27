"""Auth request/response schemas.

Never includes password_hash, raw tokens as anything other than the
access_token payload, or internal session identifiers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["traveler", "provider"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role

    # Traveler profile fields
    display_name: str = Field(min_length=1, max_length=120)
    traveler_type: str | None = Field(default=None, max_length=30)

    # Provider profile fields (required when role == "provider")
    business_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    provider_type: str | None = Field(default=None, max_length=40)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_role_fields(self) -> RegisterRequest:
        if self.role == "provider" and not self.business_name:
            raise ValueError("business_name is required when registering as a provider")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class TravelerProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    traveler_type: str | None = None


class ProviderProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    verification_status: str


class AuthResponse(BaseModel):
    """Returned by /auth/register, /auth/login, and /auth/refresh.

    The access token is meant to be held in memory only by the client —
    never persisted to localStorage/sessionStorage. The refresh token is
    never included in this body; it travels only as an HttpOnly cookie.
    """

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserPublic
    traveler: TravelerProfilePublic | None = None
    provider: ProviderProfilePublic | None = None


class MeResponse(BaseModel):
    user: UserPublic
    traveler: TravelerProfilePublic | None = None
    provider: ProviderProfilePublic | None = None
