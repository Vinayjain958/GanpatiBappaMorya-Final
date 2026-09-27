from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.interaction import TravelerInteraction


class RecommendationMetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_metrics(self, traveler_id: str | None = None) -> dict[str, object]:
        stmt = select(
            TravelerInteraction.event_type, 
            func.count(TravelerInteraction.id)
        ).group_by(TravelerInteraction.event_type)
        
        if traveler_id:
            stmt = stmt.where(TravelerInteraction.traveler_id == traveler_id)
            
        result = await self.session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        
        impressions = counts.get("IMPRESSION", 0)
        views = counts.get("VIEW", 0)
        saves = counts.get("SAVE", 0)
        completes = counts.get("COMPLETE", 0)
        skips = counts.get("SKIP", 0)

        total_interactions = sum(counts.values())
        
        # Guard against zero division
        view_rate = views / impressions if impressions > 0 else 0.0
        save_rate = saves / views if views > 0 else 0.0
        completion_rate = completes / saves if saves > 0 else 0.0
        skip_rate = skips / impressions if impressions > 0 else 0.0
        
        metrics = {
            "counts": counts,
            "total_interactions": total_interactions,
            "rates": {
                "view_rate": view_rate,
                "save_rate": save_rate,
                "completion_rate": completion_rate,
                "skip_rate": skip_rate,
            }
        }
        
        if total_interactions < 50:
            metrics["offline_ranking"] = {"status": "insufficient_data"}
        else:
            metrics["offline_ranking"] = {
                "status": "computed",
                "hit_rate_at_10": 0.0, # Placeholder for actual offline computation
                "mrr_at_10": 0.0,
                "ndcg_at_10": 0.0,
            }
            
        return metrics
