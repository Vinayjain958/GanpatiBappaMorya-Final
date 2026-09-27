"""DiscoveryPipelineService (Phase 6).

Wires SemanticRetrievalService -> FeasibilityService. Only FEASIBLE
candidates ever reach `items` — INFEASIBLE/UNKNOWN candidates are
summarized (counts by reason code, capped detail list) but never leak
into the returned feasible set (docs/AI_CONTEXT.md hard invariant).

If every candidate ends up INFEASIBLE/UNKNOWN, the pipeline returns an
empty `items` list plus the reason summary — it never forces a
lower-quality result through just to have "something" to show.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.models.experience import Experience
    from src.schemas.conversation import TravelerContext
    from src.schemas.ranking import RankedExperienceItem

from src.adapters.embedding import EmbeddingAdapter
from src.adapters.routing import RoutingAdapter
from src.core.config import Settings
from src.schemas.feasibility import FeasibilityVerdict, TravelerConstraints
from src.services.feasibility import FeasibilityService
from src.services.semantic_retrieval import SemanticRetrievalService

_EXCLUDED_DETAIL_CAP = 10


@dataclass
class PipelineItem:
    experience_id: str
    similarity: float | None
    verdict: FeasibilityVerdict
    experience: Experience


@dataclass
class ExcludedSummary:
    reason_counts: dict[str, int] = field(default_factory=dict)
    sample: list[dict[str, object]] = field(default_factory=list)


@dataclass
class DiscoveryPipelineResult:
    items: list[PipelineItem]
    retrieval_mode: str
    candidate_count: int
    feasible_count: int
    excluded_count: int
    excluded_summary: ExcludedSummary


class DiscoveryPipelineService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        embedding_adapter: EmbeddingAdapter | None,
        routing_adapter: RoutingAdapter,
    ) -> None:
        self._session = session
        self._retrieval = SemanticRetrievalService(session, settings, embedding_adapter)
        self._feasibility = FeasibilityService(routing_adapter)
        self._settings = settings

    async def run(
        self,
        *,
        raw_query: str | None,
        interests: list[str] | None = None,
        category_slug: str | None = None,
        city: str | None = None,
        locality: str | None = None,
        location_text: str | None = None,
        constraints: TravelerConstraints | None = None,
        limit: int | None = None,
        travel_profile: str = "driving",
    ) -> DiscoveryPipelineResult:
        constraints = constraints or TravelerConstraints()
        limit = limit or self._settings.semantic_result_limit

        retrieval = await self._retrieval.retrieve(
            raw_query=raw_query,
            interests=interests,
            category_slug=category_slug,
            city=city,
            locality=locality,
            location_text=location_text,
        )

        feasible: list[PipelineItem] = []
        excluded_reason_counts: Counter[str] = Counter()
        excluded_sample: list[dict[str, object]] = []
        excluded_count = 0

        for candidate in retrieval.items:
            verdict = await self._feasibility.evaluate(
                candidate.experience, constraints, travel_profile=travel_profile
            )
            if verdict.status == "FEASIBLE":
                feasible.append(
                    PipelineItem(
                        experience_id=candidate.experience.id,
                        similarity=candidate.similarity,
                        verdict=verdict,
                        experience=candidate.experience,
                    )
                )
                if len(feasible) >= limit:
                    break
            else:
                excluded_count += 1
                for reason in verdict.reasons:
                    excluded_reason_counts[reason.code.value] += 1
                if len(excluded_sample) < _EXCLUDED_DETAIL_CAP:
                    excluded_sample.append(
                        {
                            "experience_id": candidate.experience.id,
                            "status": verdict.status,
                            "reasons": [r.code.value for r in verdict.reasons],
                        }
                    )

        return DiscoveryPipelineResult(
            items=feasible,
            retrieval_mode=retrieval.retrieval_mode,
            candidate_count=retrieval.candidate_count,
            feasible_count=len(feasible),
            excluded_count=excluded_count,
            excluded_summary=ExcludedSummary(
                reason_counts=dict(excluded_reason_counts), sample=excluded_sample
            ),
        )

    async def run_with_ranking(
        self,
        traveler_id: str,
        *,
        raw_query: str | None,
        interests: list[str] | None = None,
        category_slug: str | None = None,
        city: str | None = None,
        locality: str | None = None,
        location_text: str | None = None,
        constraints: TravelerConstraints | None = None,
        limit: int | None = None,
        travel_profile: str = "driving",
        context: TravelerContext | None = None,
    ) -> tuple[DiscoveryPipelineResult, list[RankedExperienceItem]]:
        result = await self.run(
            raw_query=raw_query,
            interests=interests,
            category_slug=category_slug,
            city=city,
            locality=locality,
            location_text=location_text,
            constraints=constraints,
            limit=limit,
            travel_profile=travel_profile,
        )
        
        from src.services.ranking import PersonalizedRankingService
        ranker_service = PersonalizedRankingService(self._settings)
        
        ranked_items = await ranker_service.rank(
            traveler_id=traveler_id,
            pipeline_items=result.items,
            context=context,
            session=self._session,
        )
        
        # We replace items in result with ranked items?
        # The prompt implies run_with_ranking produces the ranked results.
        return result, ranked_items


__all__ = ["DiscoveryPipelineResult", "DiscoveryPipelineService", "ExcludedSummary", "PipelineItem"]
