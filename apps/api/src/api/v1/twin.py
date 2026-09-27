"""Read-only Digital-Twin context surfaces backed by normalized aggregates."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import CurrentUser
from src.core.db import get_session
from src.core.errors import ApiError
from src.core.social_signals import get_social_signal_service
from src.models.experience import Experience
from src.models.itinerary import Itinerary
from src.models.itinerary_item import ItineraryItem
from src.models.location import Location
from src.schemas.social_signals import SocialSignalsResponse
from src.services.social_signals import SocialSignalService

router = APIRouter(prefix="/twin", tags=["digital-twin-context"])


@router.get("/social-signals", response_model=SocialSignalsResponse)
async def get_social_signals(
    user: CurrentUser,
    service: Annotated[SocialSignalService, Depends(get_social_signal_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(ge=1, le=50)] = 10,
    topics: Annotated[str | None, Query(max_length=200)] = None,
    since_hours: Annotated[int, Query(ge=1, le=24)] = 24,
    itinerary_item_id: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
) -> SocialSignalsResponse:
    """Return area-level public signals; never return individual posts."""
    topic_list = [topic.strip().casefold() for topic in topics.split(",") if topic.strip()] if topics else None
    fallback_locality = None
    fallback_city = None
    if itinerary_item_id:
        traveler_id = user.traveler.id if user.traveler is not None else None
        if traveler_id is None:
            raise ApiError("Traveler profile not found", status_code=404)
        location_row = (await session.execute(
            select(Location.locality, Location.city, Location.latitude, Location.longitude)
            .select_from(ItineraryItem)
            .join(Itinerary, Itinerary.id == ItineraryItem.itinerary_id)
            .join(Experience, Experience.id == ItineraryItem.experience_id)
            .join(Location, Location.id == Experience.location_id)
            .where(ItineraryItem.id == itinerary_item_id, Itinerary.traveler_id == traveler_id)
        )).first()
        if location_row is None:
            raise ApiError("Itinerary stop not found", status_code=404)
        if abs(location_row.latitude - lat) > 0.0001 or abs(location_row.longitude - lng) > 0.0001:
            raise ApiError("Coordinates do not match the selected itinerary stop", status_code=422)
        fallback_locality, fallback_city = location_row.locality, location_row.city
    try:
        if fallback_locality or fallback_city:
            return await service.get_social_signals(
                lat, lng, radius_km, topic_list, since_hours,
                fallback_locality=fallback_locality,
                fallback_city=fallback_city,
            )
        return await service.get_social_signals(lat, lng, radius_km, topic_list, since_hours)
    except ValueError as exc:
        raise ApiError(str(exc), status_code=422) from exc


__all__ = ["router"]
