"""Stable, deterministic handoff contract for a future domain-intelligence provider.

The contract carries already-normalized simulation facts. Providers may add
explanatory notes, but cannot change feasibility, impact, ranking, or apply decisions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DomainIntelligenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_name: str
    impact_categories: list[str] = Field(default_factory=list)
    affected_item_ids: list[str] = Field(default_factory=list)
    weather_statuses: list[str] = Field(default_factory=list)
    route_statuses: list[str] = Field(default_factory=list)


class DomainIntelligenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["mock"] = "mock"
    summary: str
    notes: list[str] = Field(default_factory=list)
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"


__all__ = ["DomainIntelligenceInput", "DomainIntelligenceResult"]
