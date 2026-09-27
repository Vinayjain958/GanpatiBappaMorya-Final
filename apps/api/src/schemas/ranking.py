from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.experience import ExperienceSummary
from src.schemas.feasibility import TravelerConstraints
from src.schemas.semantic_search import ExcludedReasonSummary


class RankedExperienceItem(ExperienceSummary):
    model_config = ConfigDict(extra="ignore")
    
    rank: int
    ranking_score: float
    ranking_model_version: str
    semantic_relevance: float
    personalized: bool
    match_signals: list[str] = Field(default_factory=list)

class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    interests: list[str] = Field(default_factory=list)
    constraints: TravelerConstraints = Field(default_factory=TravelerConstraints)
    top_k: int = Field(default=10, ge=1, le=50)

class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RankedExperienceItem]
    retrieval_mode: str
    candidate_count: int
    feasible_count: int
    excluded_count: int
    excluded_summary: ExcludedReasonSummary
    ranking_model_version: str
    personalized: bool

__all__ = [
    "RankedExperienceItem",
    "RecommendationRequest",
    "RecommendationResponse",
]
