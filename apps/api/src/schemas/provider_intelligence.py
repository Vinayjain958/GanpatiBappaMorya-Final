from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


InsightWindow = Literal["7d", "30d", "90d"]
InsightGranularity = Literal["auto", "day", "week"]


class ProviderKPIs(BaseModel):
    """Observed KPIs only. Synthetic values are in TrendDataPoint.synthetic."""
    impressions: int
    views: int
    saves: int
    completions: int
    booking_requests: int
    accepted_bookings: int
    ratings_count: int
    average_rating: float | None
    save_rate: float
    booking_request_rate: float
    accepted_booking_rate: float


class TrendDataPoint(BaseModel):
    period_start: datetime
    period_end: datetime
    observed: dict[str, int | float | None]
    synthetic: dict[str, int | float | None]


class DemandSegment(BaseModel):
    segment_type: str
    key: str
    label: str
    interactions: int | None
    share: float | None
    trend_percent: float | None
    minimum_sample_met: bool
    is_synthetic: bool


class ExperiencePerformance(BaseModel):
    experience_id: str
    title: str
    category_slug: str
    category_name: str
    views: int
    saves: int
    completions: int
    booking_requests: int
    accepted_bookings: int
    ratings_count: int
    average_rating: float | None
    save_rate: float
    booking_rate: float
    is_synthetic: bool


class ProviderMatchSummary(BaseModel):
    match_id: str
    score: float
    model_version: str
    qualified: bool
    segment_summary: list[str]
    matched_experience_ids: list[str]
    evidence_codes: list[str]
    created_at: datetime
    is_synthetic: bool


class ActionableInsight(BaseModel):
    code: str
    title: str
    explanation: str
    supporting_metric: str
    period: str
    confidence: str
    is_synthetic: bool


class InsightProvenance(BaseModel):
    has_observed_data: bool
    has_synthetic_data: bool
    observed_interaction_count: int
    synthetic_interaction_count: int
    generated_at: datetime
    window: str
    granularity: str


class ProviderInsightResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    kpis: ProviderKPIs
    trends: list[TrendDataPoint]
    segments: list[DemandSegment]
    experience_performance: list[ExperiencePerformance]
    matches: list[ProviderMatchSummary]
    insights: list[ActionableInsight]
    provenance: InsightProvenance


class ProviderNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    body: str
    experience_id: str | None
    match_score: float | None
    segment_summary: list[str] | None
    is_read: bool
    created_at: datetime
    is_synthetic: bool
    booking_request_id: str | None


class ProviderNotificationListResponse(BaseModel):
    items: list[ProviderNotificationResponse]
    total: int
    unread_count: int
