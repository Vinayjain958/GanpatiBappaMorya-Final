"""Read-only Digital-Twin context surfaces backed by normalized aggregates."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.core.deps import CurrentUser
from src.core.errors import ApiError
from src.core.social_signals import get_social_signal_service
from src.schemas.social_signals import SocialSignalsResponse
from src.services.social_signals import SocialSignalService

router = APIRouter(prefix="/twin", tags=["digital-twin-context"])


@router.get("/social-signals", response_model=SocialSignalsResponse)
async def get_social_signals(
    _user: CurrentUser,
    service: Annotated[SocialSignalService, Depends(get_social_signal_service)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(ge=1, le=50)] = 10,
    topics: Annotated[str | None, Query(max_length=200)] = None,
    since_hours: Annotated[int, Query(ge=1, le=24)] = 24,
) -> SocialSignalsResponse:
    """Return area-level public signals; never return individual posts."""
    topic_list = [topic.strip().casefold() for topic in topics.split(",") if topic.strip()] if topics else None
    try:
        return await service.get_social_signals(lat, lng, radius_km, topic_list, since_hours)
    except ValueError as exc:
        raise ApiError(str(exc), status_code=422) from exc


__all__ = ["router"]
