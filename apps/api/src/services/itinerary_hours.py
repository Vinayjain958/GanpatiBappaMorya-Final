"""Opening-hours status and nearby open alternatives for saved itinerary stops."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.geo import bounding_box, haversine_km
from src.models.experience import Experience
from src.models.opening_hour import ExperienceOpeningHour
from src.repositories.experience_repository import ExperienceFilters, ExperienceRepository
from src.schemas.feasibility import TravelerConstraints
from src.services.feasibility import FeasibilityService

_DEFAULT_TIMEZONE = "Asia/Kolkata"
_ALTERNATIVE_RADIUS_KM = 10.0
_ALTERNATIVE_LIMIT = 3


@dataclass(frozen=True)
class NearbyOpenPlace:
    experience: Experience
    distance_km: float
    opening_hours_for_visit: list[ExperienceOpeningHour]


@dataclass(frozen=True)
class ItineraryStopOpeningStatus:
    status: Literal["open", "closed", "unknown"]
    opening_hours_for_visit: list[ExperienceOpeningHour]
    nearby_open_alternatives: list[NearbyOpenPlace]


def _local_visit_window(
    experience: Experience,
    planned_start: datetime,
    planned_end: datetime,
) -> tuple[date, time, time, str]:
    timezone_name = experience.location.timezone or _DEFAULT_TIMEZONE
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception:
        timezone_name = _DEFAULT_TIMEZONE
        timezone = ZoneInfo(timezone_name)

    # SQLite returns the app's local wall-clock schedule without tzinfo.
    # PostgreSQL's aware values are converted to the venue's timezone.
    start = planned_start.astimezone(timezone) if planned_start.tzinfo else planned_start
    end = planned_end.astimezone(timezone) if planned_end.tzinfo else planned_end
    return start.date(), start.time().replace(tzinfo=None), end.time().replace(tzinfo=None), timezone_name


def _visit_day_hours(
    experience: Experience,
    visit_date: date,
    visit_start: time,
    visit_end: time,
) -> list[ExperienceOpeningHour]:
    rows = list(experience.opening_hours)
    today = [row for row in rows if row.day_of_week == visit_date.weekday()]
    if today:
        return today

    # If the venue has an overnight window from the previous day, expose that
    # window when this stop is scheduled after midnight and before it closes.
    previous_day = (visit_date.weekday() - 1) % 7
    overnight = []
    for row in rows:
        if row.day_of_week != previous_day or row.is_closed or not row.open_time or not row.close_time:
            continue
        closes_at = time.fromisoformat(row.close_time)
        if (
            row.close_time <= row.open_time
            and visit_start < closes_at
            and visit_end <= closes_at
        ):
            overnight.append(row)
    return overnight


def _opening_status(
    experience: Experience,
    *,
    visit_date: date,
    visit_start: time,
    visit_end: time,
    timezone_name: str,
) -> Literal["open", "closed", "unknown"]:
    constraints = TravelerConstraints(
        available_date=visit_date,
        available_start=visit_start,
        available_end=visit_end,
        timezone=timezone_name,
    )
    status, _ = FeasibilityService.opening_hours_status(experience, constraints)
    return status


async def check_itinerary_stop_opening_hours(
    experience: Experience,
    *,
    planned_start: datetime,
    planned_end: datetime,
    session: AsyncSession,
    excluded_experience_ids: set[str],
) -> ItineraryStopOpeningStatus:
    """Annotate a stop and, when closed, return up to three nearby open places.

    Alternatives are active catalog records within 10 km, ranked by proximity
    with same-category places preferred. Opening-hour status is evaluated for
    the exact scheduled visit window. Unknown-hour places are never called
    open. Synthetic/demo hours remain tagged on the returned records.
    """
    visit_date, visit_start, visit_end, timezone_name = _local_visit_window(
        experience, planned_start, planned_end
    )
    status = _opening_status(
        experience,
        visit_date=visit_date,
        visit_start=visit_start,
        visit_end=visit_end,
        timezone_name=timezone_name,
    )
    hours = _visit_day_hours(experience, visit_date, visit_start, visit_end)
    if status != "closed":
        return ItineraryStopOpeningStatus(status, hours, [])

    origin = experience.location
    box = bounding_box(origin.latitude, origin.longitude, _ALTERNATIVE_RADIUS_KM)
    candidates = await ExperienceRepository(session).search(
        ExperienceFilters(
            status="active",
            min_lat=box.min_lat,
            max_lat=box.max_lat,
            min_lng=box.min_lng,
            max_lng=box.max_lng,
        ),
        cap=1000,
    )

    nearby: list[NearbyOpenPlace] = []
    for candidate in candidates:
        if candidate.id in excluded_experience_ids:
            continue
        distance = haversine_km(
            origin.latitude,
            origin.longitude,
            candidate.location.latitude,
            candidate.location.longitude,
        )
        if distance > _ALTERNATIVE_RADIUS_KM:
            continue

        candidate_timezone = candidate.location.timezone or timezone_name
        candidate_status = _opening_status(
            candidate,
            visit_date=visit_date,
            visit_start=visit_start,
            visit_end=visit_end,
            timezone_name=candidate_timezone,
        )
        if candidate_status != "open":
            continue

        nearby.append(
            NearbyOpenPlace(
                experience=candidate,
                distance_km=distance,
                opening_hours_for_visit=_visit_day_hours(
                    candidate, visit_date, visit_start, visit_end
                ),
            )
        )

    nearby.sort(
        key=lambda place: (
            place.experience.category_id != experience.category_id,
            place.distance_km,
            place.experience.title.casefold(),
        )
    )
    return ItineraryStopOpeningStatus(status, hours, nearby[:_ALTERNATIVE_LIMIT])


__all__ = [
    "ItineraryStopOpeningStatus",
    "NearbyOpenPlace",
    "check_itinerary_stop_opening_hours",
]
