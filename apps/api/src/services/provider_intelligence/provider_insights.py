from datetime import datetime, timedelta, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import Settings
from src.models.experience import Experience
from src.schemas.provider_intelligence import (
    ExperiencePerformance,
    InsightProvenance,
    ProviderInsightResponse,
    ProviderKPIs,
    TrendDataPoint,
)
from src.services.provider_intelligence.demand_signal import DemandSignalAggregationService
from src.services.provider_intelligence.insight_engine import ActionableInsightEngine
from src.services.provider_intelligence.provider_matching import ProviderTravelerMatchService
from src.services.provider_intelligence.segmentation import SegmentationService


class ProviderInsightService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.demand = DemandSignalAggregationService(session)
        self.segmentation = SegmentationService(session, settings)
        self.matching = ProviderTravelerMatchService(session, settings)
        self.insights = ActionableInsightEngine(settings)

    async def get_insights(
        self, provider_id: str, window: str, granularity: str, include_synthetic: bool = True
    ) -> ProviderInsightResponse:
        
        now = datetime.now(UTC)
        
        if window == "7d":
            period_start = now - timedelta(days=7)
        elif window == "30d":
            period_start = now - timedelta(days=30)
        elif window == "90d":
            period_start = now - timedelta(days=90)
        else:
            window = self.settings.provider_insight_default_window
            period_start = now - timedelta(days=30)
            
        period_end = now
        
        stmt = (
            select(Experience)
            .where(Experience.provider_id == provider_id)
            .options(selectinload(Experience.category))
        )
        result = await self.session.execute(stmt)
        experiences = list(result.scalars().all())
        
        provider_category_slugs = list(set([e.category_slug for e in experiences]))
        
        kpis_raw = await self.demand.aggregate_kpis(provider_id, period_start, period_end)
        kpis = ProviderKPIs(**kpis_raw)
        
        synth_kpis_raw = {"impressions": 0, "views": 0, "saves": 0, "completions": 0, "booking_requests": 0, "accepted_bookings": 0, "ratings_count": 0, "average_rating": None}
        synth_snapshots = []
        if include_synthetic:
            synth_snapshots = await self.demand.aggregate_synthetic(provider_id, period_start, period_end)
            if synth_snapshots:
                rating_sum = 0.0
                for s in synth_snapshots:
                    synth_kpis_raw["views"] += s.views
                    synth_kpis_raw["saves"] += s.saves
                    synth_kpis_raw["completions"] += s.completions
                    synth_kpis_raw["booking_requests"] += s.booking_requests
                    synth_kpis_raw["accepted_bookings"] += s.accepted_bookings
                    synth_kpis_raw["ratings_count"] += s.ratings_count
                    if s.average_rating is not None and s.ratings_count > 0:
                        rating_sum += s.average_rating * s.ratings_count
                
                if synth_kpis_raw["ratings_count"] > 0:
                    synth_kpis_raw["average_rating"] = rating_sum / synth_kpis_raw["ratings_count"]
                    
        trends_raw = await self.demand.aggregate_trends(provider_id, period_start, period_end, granularity)
        trends = [TrendDataPoint(**t) for t in trends_raw]
        
        exp_perf_raw = await self.demand.aggregate_by_experience(provider_id, period_start, period_end)
        
        exp_performances = []
        for exp in experiences:
            eid = exp.id
            raw = exp_perf_raw.get(eid, {"views": 0, "saves": 0, "completions": 0, "ratings_count": 0, "rating_sum": 0.0, "booking_requests": 0, "accepted_bookings": 0})
            
            syn_views = 0
            syn_saves = 0
            syn_comps = 0
            syn_br = 0
            syn_acc = 0
            syn_rc = 0
            syn_rs = 0.0
            is_synthetic_exp = False
            
            if include_synthetic and synth_snapshots:
                for s in synth_snapshots:
                    if s.experience_id == eid:
                        is_synthetic_exp = True
                        syn_views += s.views
                        syn_saves += s.saves
                        syn_comps += s.completions
                        syn_br += s.booking_requests
                        syn_acc += s.accepted_bookings
                        syn_rc += s.ratings_count
                        if s.average_rating and s.ratings_count > 0:
                            syn_rs += s.average_rating * s.ratings_count
            
            tot_views = raw["views"] + syn_views
            tot_saves = raw["saves"] + syn_saves
            tot_comps = raw["completions"] + syn_comps
            tot_br = raw["booking_requests"] + syn_br
            tot_acc = raw["accepted_bookings"] + syn_acc
            tot_rc = raw["ratings_count"] + syn_rc
            tot_rs = raw["rating_sum"] + syn_rs
            
            avg_rating = tot_rs / tot_rc if tot_rc > 0 else None
            save_rate = tot_saves / max(tot_views, 1)
            br_rate = tot_br / max(tot_views, 1)
            
            exp_performances.append(ExperiencePerformance(
                experience_id=eid,
                title=exp.title,
                category_slug=exp.category_slug,
                category_name=exp.category.name if exp.category else exp.category_slug,
                views=tot_views,
                saves=tot_saves,
                completions=tot_comps,
                booking_requests=tot_br,
                accepted_bookings=tot_acc,
                ratings_count=tot_rc,
                average_rating=avg_rating,
                save_rate=save_rate,
                booking_rate=br_rate,
                is_synthetic=is_synthetic_exp
            ))
            
        segments = await self.segmentation.compute_segments(provider_id, period_start, period_end, provider_category_slugs)
        
        matches = await self.matching.get_recent_matches(provider_id, limit=5)
        
        has_syn = (include_synthetic and len(synth_snapshots) > 0)
        actionable_insights = self.insights.compute_insights(kpis, trends, window, has_syn)
        
        observed_interactions = kpis.views + kpis.saves + kpis.completions + kpis.ratings_count
        syn_interactions = synth_kpis_raw["views"] + synth_kpis_raw["saves"] + synth_kpis_raw["completions"] + synth_kpis_raw["ratings_count"]
        
        provenance = InsightProvenance(
            has_observed_data=(observed_interactions > 0),
            has_synthetic_data=has_syn,
            observed_interaction_count=observed_interactions,
            synthetic_interaction_count=syn_interactions,
            generated_at=now,
            window=window,
            granularity=granularity if granularity != "auto" else ("week" if window == "90d" else "day"),
        )
        
        return ProviderInsightResponse(
            period_start=period_start,
            period_end=period_end,
            kpis=kpis,
            trends=trends,
            segments=segments,
            experience_performance=exp_performances,
            matches=matches,
            insights=actionable_insights,
            provenance=provenance
        )
