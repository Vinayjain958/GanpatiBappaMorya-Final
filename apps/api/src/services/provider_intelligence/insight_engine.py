from src.core.config import Settings
from src.schemas.provider_intelligence import ActionableInsight, ProviderKPIs, TrendDataPoint


class ActionableInsightEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def compute_insights(
        self, kpis: ProviderKPIs, trends: list[TrendDataPoint], window: str, has_synthetic: bool
    ) -> list[ActionableInsight]:
        insights = []
        
        views = kpis.views
        save_rate = kpis.save_rate
        
        if views < self.settings.provider_insight_min_segment_events:
            insights.append(ActionableInsight(
                code="INSUFFICIENT_DATA",
                title="Insufficient Data",
                explanation="There is not enough interaction data in this period to generate reliable insights.",
                supporting_metric=f"{views} views",
                period=window,
                confidence="INSUFFICIENT_DATA",
                is_synthetic=has_synthetic,
            ))
            return insights

        if save_rate > 0.15:
            conf = "HIGH" if window in ("30d", "90d") else "MEDIUM"
            insights.append(ActionableInsight(
                code="HIGH_SAVE_INTENT",
                title="High Save Intent",
                explanation="Your experiences are being saved at a high rate, indicating strong traveler interest.",
                supporting_metric=f"{save_rate*100:.1f}% save rate",
                period=window,
                confidence=conf,
                is_synthetic=has_synthetic,
            ))

        if views < 5 and window in ("30d", "90d"):
            insights.append(ActionableInsight(
                code="LOW_ACTIVITY",
                title="Low Activity",
                explanation="Your experiences have very few views over a long period. Consider updating titles or categories.",
                supporting_metric=f"{views} views",
                period=window,
                confidence="LOW",
                is_synthetic=has_synthetic,
            ))
            
        if len(trends) >= 2:
            current_trend = trends[-1]
            prev_trend = trends[-2]
            
            curr_views = current_trend.observed["views"] + current_trend.synthetic["views"]
            prev_views = prev_trend.observed["views"] + prev_trend.synthetic["views"]
            
            if prev_views > 0 and curr_views > 2 * prev_views:
                insights.append(ActionableInsight(
                    code="RISING_DEMAND",
                    title="Rising Demand",
                    explanation="Views have more than doubled compared to the previous period.",
                    supporting_metric=f"{curr_views} views vs {prev_views}",
                    period=window,
                    confidence="HIGH",
                    is_synthetic=has_synthetic,
                ))

            curr_br = current_trend.observed["booking_requests"] + current_trend.synthetic["booking_requests"]
            prev_br = prev_trend.observed["booking_requests"] + prev_trend.synthetic["booking_requests"]
            if prev_br > 0 and curr_br > 1.5 * prev_br:
                insights.append(ActionableInsight(
                    code="BOOKING_INTENT_INCREASED",
                    title="Booking Intent Increased",
                    explanation="Booking requests have increased significantly compared to the previous period.",
                    supporting_metric=f"{curr_br} requests vs {prev_br}",
                    period=window,
                    confidence="MEDIUM",
                    is_synthetic=has_synthetic,
                ))

        return insights
