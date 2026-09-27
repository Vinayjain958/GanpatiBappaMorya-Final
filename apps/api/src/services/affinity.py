from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.models.affinity import TravelerAffinity
from src.models.experience import Experience
from src.models.interaction import TravelerInteraction
from src.repositories.affinity_repository import AffinityRepository


class TravelerAffinityService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.repo = AffinityRepository(session)

    async def get_affinities(self, traveler_id: str) -> list[TravelerAffinity]:
        return await self.repo.get_by_traveler_id(traveler_id)

    def _compute_signal(self, event_type: str, rating: float | None) -> float:
        signals = {
            "IMPRESSION": 0.00,
            "VIEW": 0.05,
            "SAVE": 0.40,
            "COMPLETE": 0.60,
            "UNSAVE": -0.25,
            "SKIP": -0.20,
        }
        if event_type == "RATING" and rating is not None:
            return (rating - 3) / 2
        return signals.get(event_type, 0.0)

    def _bounded_update(self, old_score: float, signal: float, learning_rate: float) -> float:
        new_score = old_score + learning_rate * signal
        return max(-1.0, min(1.0, new_score))

    def _compute_confidence(self, interaction_count: int, tau: int) -> float:
        # Simple asymptotic confidence approaching 1.0
        if interaction_count == 0:
            return 0.0
        return 1.0 - (1.0 / (1.0 + (interaction_count / tau)))

    async def update_from_interaction(
        self, 
        interaction: TravelerInteraction, 
        experience: Experience
    ) -> TravelerAffinity | None:
        signal = self._compute_signal(interaction.event_type, interaction.rating)
        if signal == 0.0:
            return None
            
        category_slug = experience.category.slug if experience.category else None
        if not category_slug:
            return None

        affinity = await self.repo.get_by_dimension_key(
            interaction.traveler_id, 
            "category", 
            category_slug
        )
        
        old_score = affinity.score if affinity else 0.0
        old_count = affinity.interaction_count if affinity else 0
        old_pos = affinity.positive_count if affinity else 0
        old_neg = affinity.negative_count if affinity else 0
        
        new_score = self._bounded_update(old_score, signal, self.settings.affinity_learning_rate)
        new_count = old_count + 1
        new_pos = old_pos + 1 if signal > 0 else old_pos
        new_neg = old_neg + 1 if signal < 0 else old_neg
        
        new_conf = self._compute_confidence(new_count, self.settings.affinity_recency_tau)

        updates = {
            "score": new_score,
            "interaction_count": new_count,
            "positive_count": new_pos,
            "negative_count": new_neg,
            "confidence": new_conf,
        }
        
        return await self.repo.upsert(
            interaction.traveler_id, 
            "category", 
            category_slug, 
            updates
        )
