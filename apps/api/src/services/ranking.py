from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.models.affinity import TravelerAffinity
from src.models.preference import TravelerPreference
from src.repositories.affinity_repository import AffinityRepository
from src.repositories.interaction_repository import InteractionRepository
from src.repositories.preference_repository import PreferenceRepository
from src.schemas.conversation import TravelerContext
from src.schemas.ranking import RankedExperienceItem
from src.services.discovery_pipeline import PipelineItem

logger = logging.getLogger(__name__)


@dataclass
class TravelerRankingProfile:
    traveler_id: str
    preference: TravelerPreference | None
    affinities: dict[tuple[str, str], TravelerAffinity]
    recently_seen_experience_ids: set[str]


class RankerProtocol(Protocol):
    def rank(
        self,
        candidates: list[PipelineItem],
        traveler_profile: TravelerRankingProfile,
        context: TravelerContext,
        settings: Settings,
    ) -> list[RankedExperienceItem]: ...


class WeightedPersonalizedRanker:
    def rank(
        self,
        candidates: list[PipelineItem],
        traveler_profile: TravelerRankingProfile,
        context: TravelerContext,
        settings: Settings,
    ) -> list[RankedExperienceItem]:
        
        ranked_items = []
        for candidate in candidates:
            # Base Semantic Relevance
            semantic_relevance = candidate.similarity if candidate.similarity is not None else 0.5
            
            # Affinity Score
            affinity = traveler_profile.affinities.get(("category", candidate.experience.category.slug))
            affinity_score = affinity.score if affinity else 0.0
            
            # Preference Match
            preference_match = 0.0
            if traveler_profile.preference and traveler_profile.preference.preferred_category_slugs:
                if candidate.experience.category.slug in traveler_profile.preference.preferred_category_slugs:
                    preference_match = 1.0
                    
            # Budget Fit — TravelerContext carries budget_max as a flat
            # field (not a nested `constraints` object; that shape exists
            # only on TravelerConstraints, a different schema used by the
            # Phase 6 feasibility pipeline). This previously always read
            # context.constraints, which never exists on TravelerContext,
            # so the budget penalty below silently never applied.
            budget_fit = 1.0
            if context.budget_max is not None:
                if candidate.experience.price_type == "fixed" and candidate.experience.price is not None:
                    if candidate.experience.price > context.budget_max:
                        budget_fit = 0.0
            
            # Duration Fit
            duration_fit = 1.0
            
            # Distance Fit
            distance_fit = 1.0
            
            # Novelty
            novelty = 0.0 if candidate.experience_id in traveler_profile.recently_seen_experience_ids else 1.0
            
            # Calculate final score
            ranking_score = (
                settings.ranking_weight_semantic * semantic_relevance +
                settings.ranking_weight_affinity * affinity_score +
                settings.ranking_weight_preference * preference_match +
                settings.ranking_weight_budget * budget_fit +
                settings.ranking_weight_duration * duration_fit +
                settings.ranking_weight_distance * distance_fit +
                settings.ranking_weight_novelty * novelty
            )
            
            # Identify match signals
            match_signals = []
            if preference_match > 0:
                match_signals.append("Matches your preferences")
            if affinity_score > 0.5:
                match_signals.append("High affinity category")
            if novelty == 1.0 and affinity_score > 0.0:
                match_signals.append("New for you")
            if not match_signals and semantic_relevance >= 0.5:
                # No personalization signal fired (new/anonymous traveler) —
                # fall back to a relevance-based signal rather than leaving
                # match_signals empty for every non-personalized result.
                match_signals.append("Relevant to your search")
                
            is_personalized = bool(traveler_profile.preference or traveler_profile.affinities)
                
            # Field set matches schemas.experience.ExperienceSummary exactly
            # (RankedExperienceItem extends it) — see src/schemas/experience.py.
            # getattr fallbacks accommodate both a real ORM Experience and a
            # pre-built ExperienceSummary (e.g. in unit tests) as `candidate.experience`.
            exp_dict = {
                "id": candidate.experience.id,
                "title": candidate.experience.title,
                "short_description": candidate.experience.short_description,
                "category": candidate.experience.category,
                "location": candidate.experience.location,
                "provider": candidate.experience.provider,
                "currency": getattr(candidate.experience, "currency", "INR"),
                "price": getattr(candidate.experience, "price", None),
                "minimum_price": getattr(candidate.experience, "minimum_price", None),
                "maximum_price": getattr(candidate.experience, "maximum_price", None),
                "price_type": getattr(candidate.experience, "price_type", "unknown"),
                "is_price_estimated": getattr(candidate.experience, "is_price_estimated", False),
                "duration_minutes": getattr(candidate.experience, "duration_minutes", None),
                "duration_is_estimated": getattr(candidate.experience, "duration_is_estimated", False),
                "rating": getattr(candidate.experience, "rating", None),
                "rating_source": getattr(candidate.experience, "rating_source", None),
                "review_count": getattr(candidate.experience, "review_count", None),
                "status": getattr(candidate.experience, "status", "active"),
                "verification_status": getattr(candidate.experience, "verification_status", "verified"),
                "is_synthetic": getattr(candidate.experience, "is_synthetic", True),
                "is_enriched": getattr(candidate.experience, "is_enriched", False),
            }
                
            ranked_item = RankedExperienceItem(
                **exp_dict,
                rank=0, # Set later after sort
                ranking_score=ranking_score,
                ranking_model_version=settings.ranking_model_version,
                semantic_relevance=semantic_relevance,
                personalized=is_personalized,
                match_signals=match_signals
            )
            ranked_items.append(ranked_item)
            
        ranked_items.sort(key=lambda x: x.id) # 3. id asc
        ranked_items.sort(key=lambda x: x.semantic_relevance, reverse=True) # 2. semantic desc
        ranked_items.sort(key=lambda x: x.ranking_score, reverse=True) # 1. score desc
        
        for i, item in enumerate(ranked_items):
            item.rank = i + 1
            
        return ranked_items


class PersonalizedRankingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ranker = WeightedPersonalizedRanker()

    async def rank(
        self,
        traveler_id: str,
        pipeline_items: list[PipelineItem],
        context: TravelerContext | None,
        session: AsyncSession,
    ) -> list[RankedExperienceItem]:
        if not traveler_id:
            raise ValueError("traveler_id is required")
            
        if not context:
            # Not every ranking caller has a TravelerContext (e.g. the
            # direct /recommendations endpoint has no conversational
            # context) — raw_query is required by the schema for the
            # conversational path, so synthesize an empty one rather than
            # weakening TravelerContext for every other caller.
            context = TravelerContext(raw_query="")
            
        pref_repo = PreferenceRepository(session)
        preference = await pref_repo.get_by_traveler_id(traveler_id)
        
        aff_repo = AffinityRepository(session)
        affinities_list = await aff_repo.get_by_traveler_id(traveler_id)
        affinities_dict = {
            (aff.dimension_type, aff.dimension_key): aff 
            for aff in affinities_list
        }
        
        inter_repo = InteractionRepository(session)
        recent_interactions = await inter_repo.get_recent_for_traveler(
            traveler_id, 
            event_types=["VIEW", "SAVE", "COMPLETE"], 
            limit=50
        )
        recently_seen = {i.experience_id for i in recent_interactions}
        
        profile = TravelerRankingProfile(
            traveler_id=traveler_id,
            preference=preference,
            affinities=affinities_dict,
            recently_seen_experience_ids=recently_seen
        )
        
        return self.ranker.rank(
            candidates=pipeline_items,
            traveler_profile=profile,
            context=context,
            settings=self.settings
        )
