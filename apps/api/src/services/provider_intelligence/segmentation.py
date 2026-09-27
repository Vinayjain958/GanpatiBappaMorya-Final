from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.models.affinity import TravelerAffinity
from src.models.experience import Experience
from src.models.interaction import TravelerInteraction
from src.models.preference import TravelerPreference
from src.schemas.provider_intelligence import DemandSegment


class SegmentationService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings

    async def compute_segments(
        self, provider_id: str, period_start: datetime, period_end: datetime, provider_category_slugs: list[str]
    ) -> list[DemandSegment]:
        
        interacting_stmt = (
            select(TravelerInteraction.traveler_id)
            .join(Experience, TravelerInteraction.experience_id == Experience.id)
            .where(
                Experience.provider_id == provider_id,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) >= period_start,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) < period_end,
            )
            .distinct()
        )
        result = await self.session.execute(interacting_stmt)
        interacting_traveler_ids = list(result.scalars().all())

        if not interacting_traveler_ids:
            return []

        pref_stmt = select(TravelerPreference).where(
            TravelerPreference.traveler_id.in_(interacting_traveler_ids)
        )
        pref_result = await self.session.execute(pref_stmt)
        preferences = pref_result.scalars().all()

        aff_stmt = (
            select(TravelerAffinity)
            .where(
                TravelerAffinity.traveler_id.in_(interacting_traveler_ids),
                TravelerAffinity.dimension_type == "category",
                TravelerAffinity.dimension_key.in_(provider_category_slugs),
            )
        )
        aff_result = await self.session.execute(aff_stmt)
        affinities = aff_result.scalars().all()

        ts_stmt = (
            select(
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at).label("ts")
            )
            .join(Experience, TravelerInteraction.experience_id == Experience.id)
            .where(
                Experience.provider_id == provider_id,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) >= period_start,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) < period_end,
            )
        )
        ts_result = await self.session.execute(ts_stmt)
        timestamps = ts_result.scalars().all()

        segments = []
        
        budget_counts = {"budget": 0, "mid": 0, "premium": 0}
        total_prefs = len(preferences)
        for pref in preferences:
            budget_counts[pref.budget_sensitivity] = budget_counts.get(pref.budget_sensitivity, 0) + 1
        
        for k, v in budget_counts.items():
            segments.append(self._build_segment("budget_band", k, k.title(), v, total_prefs))
            
        duration_counts = {"< 60 min": 0, "1-3 hrs": 0, "3+ hrs": 0}
        for pref in preferences:
            m = pref.preferred_duration_minutes
            if m < 60: duration_counts["< 60 min"] += 1
            elif m <= 180: duration_counts["1-3 hrs"] += 1
            else: duration_counts["3+ hrs"] += 1
        
        for k, v in duration_counts.items():
            segments.append(self._build_segment("duration_band", k, k, v, total_prefs))

        cat_counts = {slug: 0 for slug in provider_category_slugs}
        for aff in affinities:
            cat_counts[aff.dimension_key] = cat_counts.get(aff.dimension_key, 0) + 1
                
        total_aff = len(interacting_traveler_ids)
        for k, v in cat_counts.items():
            segments.append(self._build_segment("category", k, k.replace("-", " ").title(), v, total_aff))
            
        daypart_counts = {"Morning": 0, "Afternoon": 0, "Evening": 0, "Night": 0}
        total_hours = len(timestamps)
        for ts in timestamps:
            h = ts.hour if ts else 0
            if 5 <= h < 12: daypart_counts["Morning"] += 1
            elif 12 <= h < 17: daypart_counts["Afternoon"] += 1
            elif 17 <= h < 21: daypart_counts["Evening"] += 1
            else: daypart_counts["Night"] += 1

        for k, v in daypart_counts.items():
            segments.append(self._build_segment("daypart", k, k, v, total_hours))
            
        return [s for s in segments if s is not None]

    def _build_segment(self, segment_type: str, key: str, label: str, count: int, total: int) -> DemandSegment | None:
        if count == 0 and total == 0:
            return None
        min_met = count >= self.settings.provider_insight_min_segment_events
        return DemandSegment(
            segment_type=segment_type,
            key=key,
            label=label,
            interactions=count if min_met else None,
            share=(count / total if total > 0 else 0.0) if min_met else None,
            trend_percent=None,
            minimum_sample_met=min_met,
            is_synthetic=False,
        )
