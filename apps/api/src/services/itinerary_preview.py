"""Date-specific, non-persisting itinerary previews for Trips.

Plans are scheduled and checked against the same catalog facts, route
adapter, feasibility service, hours, availability, budget, and window used
by composition. A preview never creates an itinerary or booking.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.errors import AdapterError
from src.adapters.routing import RoutingAdapter
from src.core.config import Settings
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.models.experience import Experience
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.feasibility import TravelerConstraints
from src.schemas.itinerary import (
    ComposeItineraryRequest,
    CompositionValidationIssue,
    ItineraryPreviewResponse,
    PreviewItineraryItem,
)
from src.services.feasibility import FeasibilityService

_DEFAULT_TZ = "Asia/Kolkata"


def _effective_price(experience: Experience) -> float | None:
    if experience.price is not None:
        return experience.price
    if experience.maximum_price is not None:
        return experience.maximum_price
    return experience.minimum_price


def _buffer(settings: Settings, pace: str, *, has_previous: bool) -> int:
    if not has_previous:
        return settings.composer_min_buffer_minutes
    return {
        "relaxed": max(settings.composer_min_buffer_minutes, 25),
        "balanced": settings.composer_min_buffer_minutes,
        "packed": min(settings.composer_min_buffer_minutes, 5),
    }.get(pace, settings.composer_min_buffer_minutes)


def _issue(code: str, constraint: str, message: str, **evidence: object) -> CompositionValidationIssue:
    return CompositionValidationIssue(
        code=code, constraint=constraint, message=message, evidence=evidence
    )


async def preview_itinerary_plans(
    *,
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    base: ComposeItineraryRequest,
    plans: list[list[str]],
) -> list[ItineraryPreviewResponse]:
    """Validate up to 200 ordered combinations using one shared catalog load
    and route matrix. No plan is saved.
    """
    repository = ExperienceRepository(session)
    unique_ids = list(dict.fromkeys(experience_id for plan in plans for experience_id in plan))
    loaded: dict[str, Experience] = {}
    for experience_id in unique_ids:
        experience = await repository.get_by_id(experience_id)
        if experience is not None:
            loaded[experience_id] = experience

    # Fetch pairwise route facts once per source stop (rather than once for
    # every combination). Missing entries remain unknown and block a plan.
    routes: dict[tuple[str, str], tuple[float, float, str]] = {}
    unique_experiences = list(loaded.values())
    chunk_size = max(1, min(settings.osrm_max_matrix_destinations, 100))
    for origin in unique_experiences:
        destinations = [
            (destination.id, destination.location.latitude, destination.location.longitude)
            for destination in unique_experiences
            if destination.id != origin.id
        ]
        for offset in range(0, len(destinations), chunk_size):
            try:
                entries = await routing_adapter.get_travel_time_matrix(
                    (origin.location.latitude, origin.location.longitude),
                    destinations[offset : offset + chunk_size],
                    profile=base.travel_mode,
                )
            except (AdapterError, ValueError):
                continue
            for entry in entries:
                if entry.duration_minutes is not None and entry.distance_km is not None:
                    routes[(origin.id, entry.id)] = (
                        entry.duration_minutes,
                        entry.distance_km,
                        entry.source if entry.source in ("osrm", "haversine_estimate") else "haversine_estimate",
                    )

    feasibility = FeasibilityService(routing_adapter)
    timezone = ZoneInfo(_DEFAULT_TZ)
    window_start = datetime.combine(base.itinerary_date, base.start_time, tzinfo=timezone)
    window_end = datetime.combine(base.itinerary_date, base.end_time, tzinfo=timezone)
    output: list[ItineraryPreviewResponse] = []

    for experience_ids in plans:
        issues: list[CompositionValidationIssue] = []
        items: list[PreviewItineraryItem] = []
        visit_minutes = 0
        total_travel: float | None = 0.0
        travel_sources: set[str] = set()
        total_cost = 0.0
        costs_known = True
        has_estimated_cost = False
        demo_schedule_used = False
        cursor = window_start
        previous: Experience | None = None

        if base.max_experiences is not None and len(experience_ids) > base.max_experiences:
            issues.append(_issue(
                FeasibilityReasonCode.ITINERARY_COUNT_LIMIT_EXCEEDED.value,
                "max_experiences",
                "This plan has more catalog stops than the selected maximum.",
                count=len(experience_ids), max_experiences=base.max_experiences,
            ))

        for _sequence, experience_id in enumerate(experience_ids, start=1):
            experience = loaded.get(experience_id)
            if experience is None:
                issues.append(_issue(
                    FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE.value,
                    "catalog",
                    "A place in this suggestion is no longer available in the catalog.",
                    experience_id=experience_id,
                ))
                continue
            if experience.duration_minutes is None:
                issues.append(_issue(
                    FeasibilityReasonCode.DURATION_UNAVAILABLE.value,
                    "duration",
                    f"{experience.title} has no recorded visit duration.",
                    experience_id=experience.id,
                ))
                continue

            demo_schedule_used = demo_schedule_used or any(
                hour.is_synthetic for hour in experience.opening_hours
            ) or any(slot.is_synthetic for slot in experience.availability_slots)

            travel_minutes: float | None = None
            travel_distance: float | None = None
            source: str | None = None
            if previous is not None:
                route = routes.get((previous.id, experience.id))
                if route is None:
                    issues.append(_issue(
                        FeasibilityReasonCode.TRAVEL_TIME_UNAVAILABLE.value,
                        "travel_time",
                        f"Travel time from {previous.title} to {experience.title} could not be checked.",
                        from_experience_id=previous.id, to_experience_id=experience.id,
                    ))
                    total_travel = None
                else:
                    travel_minutes, travel_distance, source = route
                    if total_travel is not None:
                        total_travel += travel_minutes
                    travel_sources.add(source)
                    cursor += timedelta(minutes=travel_minutes + _buffer(settings, base.pace, has_previous=True))
            else:
                cursor += timedelta(minutes=_buffer(settings, base.pace, has_previous=False))

            planned_end = cursor + timedelta(minutes=experience.duration_minutes)
            if planned_end > window_end:
                issues.append(_issue(
                    FeasibilityReasonCode.OUTSIDE_REQUESTED_WINDOW.value,
                    "window",
                    f"{experience.title} would end after the selected itinerary window.",
                    experience_id=experience.id,
                    planned_end=planned_end.isoformat(),
                    requested_end=window_end.isoformat(),
                ))

            constraints = TravelerConstraints(
                available_date=base.itinerary_date,
                available_start=cursor.timetz().replace(tzinfo=None),
                available_end=planned_end.timetz().replace(tzinfo=None),
                timezone=_DEFAULT_TZ,
                party_size=base.party_size,
                accessibility_requirements=base.accessibility_requirements,
                travel_mode=base.travel_mode,
            )
            verdict = await feasibility.evaluate(experience, constraints, travel_profile=base.travel_mode)
            for reason in verdict.reasons:
                issues.append(_issue(
                    reason.code.value,
                    reason.constraint,
                    reason.message,
                    experience_id=experience.id,
                    **reason.evidence,
                ))

            price = _effective_price(experience)
            has_estimated_cost = has_estimated_cost or experience.is_price_estimated
            if price is None:
                costs_known = False
            else:
                total_cost += price
            items.append(PreviewItineraryItem(
                experience_id=experience.id,
                title=experience.title,
                kind="place",
                planned_start=cursor,
                planned_end=planned_end,
                duration_minutes=experience.duration_minutes,
                travel_from_previous_minutes=travel_minutes,
                travel_from_previous_distance_km=travel_distance,
                travel_time_source=source,
                estimated_cost=price,
            ))
            visit_minutes += experience.duration_minutes
            cursor = planned_end
            previous = experience

        for custom in base.custom_activities:
            custom_start = datetime.combine(base.itinerary_date, custom.start_time, tzinfo=timezone)
            custom_end = custom_start + timedelta(minutes=custom.duration_minutes)
            if custom.duration_minutes:
                for item in items:
                    if custom_start < item.planned_end and item.planned_start < custom_end:
                        issues.append(_issue(
                            "CUSTOM_ACTIVITY_CONFLICT",
                            "schedule",
                            f"{custom.title} overlaps {item.title}.",
                            client_id=custom.client_id,
                            experience_id=item.experience_id,
                        ))
                if custom.kind in ("place", "activity"):
                    issues.append(_issue(
                        "CUSTOM_TRAVEL_UNVERIFIED",
                        "travel_time",
                        f"Travel to or from your custom stop {custom.title} is not in the place catalog.",
                        client_id=custom.client_id,
                    ))
            custom_price = custom.estimated_cost
            has_estimated_cost = has_estimated_cost or custom_price is not None
            if custom_price is None:
                costs_known = False
            else:
                total_cost += custom_price
            items.append(PreviewItineraryItem(
                client_id=custom.client_id,
                title=custom.title,
                kind=custom.kind,
                planned_start=custom_start,
                planned_end=custom_end,
                duration_minutes=custom.duration_minutes,
                estimated_cost=custom_price,
            ))
            visit_minutes += custom.duration_minutes

        ordered_intervals = sorted(
            (item.planned_start, item.planned_end, item.title) for item in items if item.duration_minutes > 0
        )
        for (_, prior_end, prior_title), (next_start, _, next_title) in zip(
            ordered_intervals, ordered_intervals[1:], strict=False
        ):
            if next_start < prior_end:
                issues.append(_issue(
                    "CUSTOM_ACTIVITY_CONFLICT",
                    "schedule",
                    f"{next_title} overlaps {prior_title}.",
                ))

        if base.max_budget is not None:
            if not costs_known:
                issues.append(_issue(
                    FeasibilityReasonCode.PRICE_UNAVAILABLE.value,
                    "budget",
                    "At least one stop has no price, so the total cannot be checked against your budget.",
                ))
            elif total_cost > base.max_budget:
                issues.append(_issue(
                    FeasibilityReasonCode.ITINERARY_BUDGET_EXCEEDED.value,
                    "budget",
                    f"The plan costs ₹{round(total_cost)} and exceeds your ₹{round(base.max_budget)} budget.",
                    total_cost=total_cost,
                    max_budget=base.max_budget,
                ))

        items.sort(key=lambda item: (item.planned_start, item.experience_id or item.client_id or ""))
        travel_source = None
        if "haversine_estimate" in travel_sources:
            travel_source = "haversine_estimate"
        elif "osrm" in travel_sources:
            travel_source = "osrm"
        final_end = max((item.planned_end for item in items), default=window_start)
        output.append(ItineraryPreviewResponse(
            valid=not issues,
            experience_ids=experience_ids,
            items=items,
            visit_minutes=visit_minutes,
            travel_minutes=round(total_travel, 1) if total_travel is not None else None,
            total_minutes=max(0, int((final_end - window_start).total_seconds() // 60)),
            estimated_total_cost=round(total_cost, 2) if costs_known else None,
            has_estimated_cost=has_estimated_cost,
            travel_time_source=travel_source,
            issues=issues,
            demo_schedule_used=demo_schedule_used,
        ))

    return output


__all__ = ["preview_itinerary_plans"]
