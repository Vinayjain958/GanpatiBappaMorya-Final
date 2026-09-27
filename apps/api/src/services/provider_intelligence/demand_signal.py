from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.booking_request import BookingRequest
from src.models.experience import Experience
from src.models.interaction import TravelerInteraction
from src.models.provider_synthetic_demand import ProviderSyntheticDemandSnapshot


class DemandSignalAggregationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def aggregate_kpis(
        self, provider_id: str, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        stmt = (
            select(
                TravelerInteraction.experience_id,
                TravelerInteraction.event_type,
                func.count().label("cnt"),
                func.avg(TravelerInteraction.rating).label("avg_rating"),
            )
            .join(Experience, TravelerInteraction.experience_id == Experience.id)
            .where(
                Experience.provider_id == provider_id,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) >= period_start,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) < period_end,
            )
            .group_by(TravelerInteraction.experience_id, TravelerInteraction.event_type)
        )
        
        result = await self.session.execute(stmt)
        rows = result.all()

        impressions = 0
        views = 0
        saves = 0
        completions = 0
        ratings_count = 0
        rating_sum = 0.0

        for row in rows:
            event_type = row.event_type
            cnt = row.cnt
            if event_type == "IMPRESSION":
                impressions += cnt
            elif event_type == "VIEW":
                views += cnt
            elif event_type == "SAVE":
                saves += cnt
            elif event_type == "COMPLETE":
                completions += cnt
            elif event_type == "RATING":
                ratings_count += cnt
                if row.avg_rating is not None:
                    rating_sum += row.avg_rating * cnt

        avg_rating = rating_sum / ratings_count if ratings_count > 0 else None

        booking_stmt = (
            select(
                BookingRequest.experience_id,
                BookingRequest.status,
                func.count().label("cnt"),
            )
            .where(
                BookingRequest.provider_id == provider_id,
                BookingRequest.requested_at >= period_start,
                BookingRequest.requested_at < period_end,
            )
            .group_by(BookingRequest.experience_id, BookingRequest.status)
        )
        booking_result = await self.session.execute(booking_stmt)
        booking_rows = booking_result.all()

        booking_requests = 0
        accepted_bookings = 0

        for row in booking_rows:
            if row.status == "REQUESTED":
                booking_requests += row.cnt
            elif row.status == "ACCEPTED":
                accepted_bookings += row.cnt
        
        save_rate = saves / max(views, 1)
        booking_request_rate = booking_requests / max(views, 1)
        accepted_booking_rate = accepted_bookings / max(booking_requests, 1)

        return {
            "impressions": impressions,
            "views": views,
            "saves": saves,
            "completions": completions,
            "booking_requests": booking_requests,
            "accepted_bookings": accepted_bookings,
            "ratings_count": ratings_count,
            "average_rating": avg_rating,
            "save_rate": save_rate,
            "booking_request_rate": booking_request_rate,
            "accepted_booking_rate": accepted_booking_rate,
        }

    async def aggregate_synthetic(
        self, provider_id: str, period_start: datetime, period_end: datetime
    ) -> list[ProviderSyntheticDemandSnapshot]:
        stmt = (
            select(ProviderSyntheticDemandSnapshot)
            .where(
                ProviderSyntheticDemandSnapshot.provider_id == provider_id,
                ProviderSyntheticDemandSnapshot.period_end > period_start,
                ProviderSyntheticDemandSnapshot.period_start < period_end,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_trends(
        self, provider_id: str, period_start: datetime, period_end: datetime, granularity: str
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                TravelerInteraction.event_type,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at).label("ts"),
                TravelerInteraction.rating,
            )
            .join(Experience, TravelerInteraction.experience_id == Experience.id)
            .where(
                Experience.provider_id == provider_id,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) >= period_start,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) < period_end,
            )
        )
        result = await self.session.execute(stmt)
        interaction_rows = result.all()

        booking_stmt = (
            select(
                BookingRequest.status,
                BookingRequest.requested_at,
            )
            .where(
                BookingRequest.provider_id == provider_id,
                BookingRequest.requested_at >= period_start,
                BookingRequest.requested_at < period_end,
            )
        )
        booking_result = await self.session.execute(booking_stmt)
        booking_rows = booking_result.all()
        
        synth_rows = await self.aggregate_synthetic(provider_id, period_start, period_end)

        if granularity == "auto":
            if (period_end - period_start).days > 31:
                granularity = "week"
            else:
                granularity = "day"

        buckets = []
        curr = period_start
        while curr < period_end:
            nxt = curr + timedelta(days=7) if granularity == "week" else curr + timedelta(days=1)
            if nxt > period_end:
                nxt = period_end
            
            buckets.append({
                "start": curr, 
                "end": nxt, 
                "obs": {"views": 0, "saves": 0, "completions": 0, "booking_requests": 0, "accepted_bookings": 0, "ratings_count": 0, "rating_sum": 0.0}, 
                "syn": {"views": 0, "saves": 0, "completions": 0, "booking_requests": 0, "accepted_bookings": 0, "ratings_count": 0, "rating_sum": 0.0}
            })
            curr = nxt

        for row in interaction_rows:
            ts = row.ts
            for b in buckets:
                if b["start"] <= ts < b["end"]:
                    if row.event_type == "VIEW": b["obs"]["views"] += 1
                    elif row.event_type == "SAVE": b["obs"]["saves"] += 1
                    elif row.event_type == "COMPLETE": b["obs"]["completions"] += 1
                    elif row.event_type == "RATING": 
                        b["obs"]["ratings_count"] += 1
                        if row.rating is not None: b["obs"]["rating_sum"] += row.rating
                    break

        for row in booking_rows:
            ts = row.requested_at
            for b in buckets:
                if b["start"] <= ts < b["end"]:
                    if row.status == "REQUESTED": b["obs"]["booking_requests"] += 1
                    elif row.status == "ACCEPTED": b["obs"]["accepted_bookings"] += 1
                    break
        
        for syn in synth_rows:
            for b in buckets:
                if b["start"] <= syn.period_start < b["end"]:
                    b["syn"]["views"] += syn.views
                    b["syn"]["saves"] += syn.saves
                    b["syn"]["completions"] += syn.completions
                    b["syn"]["booking_requests"] += syn.booking_requests
                    b["syn"]["accepted_bookings"] += syn.accepted_bookings
                    b["syn"]["ratings_count"] += syn.ratings_count
                    if syn.average_rating is not None and syn.ratings_count > 0:
                        b["syn"]["rating_sum"] += syn.average_rating * syn.ratings_count
                    break

        results = []
        for b in buckets:
            avg_rating = b["obs"]["rating_sum"] / b["obs"]["ratings_count"] if b["obs"]["ratings_count"] > 0 else None
            obs_data = {
                "views": b["obs"]["views"],
                "saves": b["obs"]["saves"],
                "completions": b["obs"]["completions"],
                "booking_requests": b["obs"]["booking_requests"],
                "accepted_bookings": b["obs"]["accepted_bookings"],
                "ratings_count": b["obs"]["ratings_count"],
                "average_rating": avg_rating
            }
            syn_avg_rating = b["syn"]["rating_sum"] / b["syn"]["ratings_count"] if b["syn"]["ratings_count"] > 0 else None
            syn_data = {
                "views": b["syn"]["views"],
                "saves": b["syn"]["saves"],
                "completions": b["syn"]["completions"],
                "booking_requests": b["syn"]["booking_requests"],
                "accepted_bookings": b["syn"]["accepted_bookings"],
                "ratings_count": b["syn"]["ratings_count"],
                "average_rating": syn_avg_rating
            }
            results.append({
                "period_start": b["start"],
                "period_end": b["end"],
                "observed": obs_data,
                "synthetic": syn_data,
            })
        return results

    async def aggregate_by_experience(
        self, provider_id: str, period_start: datetime, period_end: datetime
    ) -> dict[str, dict[str, Any]]:
        stmt = (
            select(
                TravelerInteraction.experience_id,
                TravelerInteraction.event_type,
                func.count().label("cnt"),
                func.avg(TravelerInteraction.rating).label("avg_rating"),
            )
            .join(Experience, TravelerInteraction.experience_id == Experience.id)
            .where(
                Experience.provider_id == provider_id,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) >= period_start,
                func.coalesce(TravelerInteraction.occurred_at, TravelerInteraction.created_at) < period_end,
            )
            .group_by(TravelerInteraction.experience_id, TravelerInteraction.event_type)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        exp_data = {}
        for row in rows:
            eid = row.experience_id
            if eid not in exp_data:
                exp_data[eid] = {"views": 0, "saves": 0, "completions": 0, "ratings_count": 0, "rating_sum": 0.0, "booking_requests": 0, "accepted_bookings": 0}
            if row.event_type == "VIEW": exp_data[eid]["views"] += row.cnt
            elif row.event_type == "SAVE": exp_data[eid]["saves"] += row.cnt
            elif row.event_type == "COMPLETE": exp_data[eid]["completions"] += row.cnt
            elif row.event_type == "RATING": 
                exp_data[eid]["ratings_count"] += row.cnt
                if row.avg_rating is not None:
                    exp_data[eid]["rating_sum"] += row.avg_rating * row.cnt
        
        booking_stmt = (
            select(
                BookingRequest.experience_id,
                BookingRequest.status,
                func.count().label("cnt"),
            )
            .where(
                BookingRequest.provider_id == provider_id,
                BookingRequest.requested_at >= period_start,
                BookingRequest.requested_at < period_end,
            )
            .group_by(BookingRequest.experience_id, BookingRequest.status)
        )
        booking_result = await self.session.execute(booking_stmt)
        b_rows = booking_result.all()

        for row in b_rows:
            eid = row.experience_id
            if eid not in exp_data:
                exp_data[eid] = {"views": 0, "saves": 0, "completions": 0, "ratings_count": 0, "rating_sum": 0.0, "booking_requests": 0, "accepted_bookings": 0}
            if row.status == "REQUESTED": exp_data[eid]["booking_requests"] += row.cnt
            elif row.status == "ACCEPTED": exp_data[eid]["accepted_bookings"] += row.cnt

        return exp_data
