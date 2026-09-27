"""Nugen chat-completion wire schemas and normalized response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NugenMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: str
    content: str


class NugenChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str
    messages: list[NugenMessage]
    max_tokens: int = 800
    temperature: float = 0.2
    stream: bool = False


class NugenChatResult(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    content: str
    model: str | None = None
    usage: dict[str, Any] | None = None
    confidence_score: float | None = Field(default=None, allow_inf_nan=False)
    finish_reason: str | None = None


__all__ = ["NugenChatRequest", "NugenChatResult", "NugenMessage"]
