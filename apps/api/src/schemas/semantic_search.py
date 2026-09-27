"""Semantic search request/response schemas (Phase 6).

POST /api/v1/experiences/semantic-search request/response shapes. Only
FEASIBLE candidates ever appear in `items` — see DiscoveryPipelineService.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.experience import ExperienceSummary
from src.schemas.feasibility import TravelerConstraints


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=2000)
    interests: list[str] = Field(default_factory=list)
    category_slug: str | None = None
    city: str | None = None
    locality: str | None = None
    location_text: str | None = None
    constraints: TravelerConstraints = Field(default_factory=TravelerConstraints)
    limit: int = Field(default=5, ge=1, le=20)


class SemanticSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience: ExperienceSummary
    semantic_similarity: float | None = None


class ExcludedReasonSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_counts: dict[str, int] = Field(default_factory=dict)
    sample: list[dict[str, object]] = Field(default_factory=list)


class SemanticSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SemanticSearchItem]
    retrieval_mode: str
    candidate_count: int
    feasible_count: int
    excluded_count: int
    excluded_summary: ExcludedReasonSummary


__all__ = [
    "ExcludedReasonSummary",
    "SemanticSearchItem",
    "SemanticSearchRequest",
    "SemanticSearchResponse",
]
