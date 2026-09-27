from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.routing import RoutingAdapter
from src.core.config import Settings
from src.core.errors import ApiError
from src.models.collab import (
    CollabGroup,
    CollabItinerary,
    CollabItineraryItem,
    CollabItineraryTrip,
)
from src.models.itinerary import Itinerary
from src.models.itinerary_item import ItineraryItem
from src.models.traveler import Traveler
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.experience import ExperienceSummary
from src.schemas.feasibility import TravelerConstraints
from src.schemas.ranking import RankedExperienceItem
from src.services.collab.groups import group_response
from src.services.collab.recommendations import member_constraints, real_schedule_evidence
from src.services.collab_preferences import score_group_experience
from src.services.experience_composer import ExperienceComposerService
from src.services.feasibility import FeasibilityService
from src.services.itinerary_narrator import ItineraryNarratorService
from src.services.itinerary_validator import ItineraryValidatorService

_GROUP_TZ = ZoneInfo("Asia/Kolkata")
_COLLAB_RANKING_VERSION = "collab-group-v1"


async def finalize_collab_plan(
    *,
    session: AsyncSession,
    settings: Settings,
    routing: RoutingAdapter,
    ai: AIAdapter,
    group: CollabGroup,
    plan: CollabItinerary,
    active_members: list[Any],
    plan_items: list[CollabItineraryItem],
    requester_member: Any,
) -> list[Itinerary]:
    existing_links = list(
        (await session.scalars(
            select(CollabItineraryTrip).where(CollabItineraryTrip.collab_itinerary_id == plan.id)
        )).all()
    )
    if plan.status == "FINALIZED":
        return list(
            (await session.scalars(
                select(Itinerary).where(Itinerary.id.in_([link.itinerary_id for link in existing_links]))
            )).all()
        )
    if group.itinerary_date is None or group.start_time is None or group.end_time is None:
        raise ApiError("Set the group date and start/end times before finalizing", status_code=422)
    if not plan_items:
        raise ApiError("Add at least one itinerary activity before finalizing", status_code=422)

    snapshot = await group_response(session, group, requester_member)
    if any(member.hard_constraints.get("age") is not None for member in snapshot.members):
        raise ApiError(
            "Member ages are present, but the catalog has no verified age-limit data. Remove age constraints or provide verified age-limit fields before finalizing.",
            status_code=422,
        )

    hard = [member.hard_constraints for member in snapshot.members]
    budgets = [row["budget_max"] for row in hard if row.get("budget_max") is not None]
    max_budget = min(budgets) if budgets else None
    party_size = len(active_members)
    required_items = [item for item in plan_items if not item.is_optional]
    if not required_items:
        raise ApiError("The plan needs at least one required activity; optional items stay as branches", status_code=422)

    exp_repo = ExperienceRepository(session)
    ranked_candidates: list[RankedExperienceItem] = []
    experiences_by_id = {}
    for index, plan_item in enumerate(required_items, start=1):
        experience = await exp_repo.get_by_id(plan_item.experience_id)
        if (
            experience is None
            or experience.status != "active"
            or experience.is_synthetic
            or experience.provider.is_synthetic
            or experience.location.is_synthetic
        ):
            raise ApiError("A selected activity is no longer a real, active catalog experience", status_code=409)
        score = score_group_experience(
            experience,
            [
                {
                    "id": member.id,
                    "email": member.email,
                    "soft_preferences": member.soft_preferences,
                    "hard_constraints": member.hard_constraints,
                }
                for member in snapshot.members
            ],
            group.objectives or {},
        )
        summary = ExperienceSummary.model_validate(experience)
        ranked_candidates.append(
            RankedExperienceItem.model_validate(
                {
                    **summary.model_dump(),
                    "rank": index,
                    "ranking_score": score["compatibility_score"] / 100,
                    "ranking_model_version": _COLLAB_RANKING_VERSION,
                    "semantic_relevance": 0.0,
                    "personalized": False,
                    "match_signals": score["matched_preferences"],
                }
            )
        )
        experiences_by_id[experience.id] = experience

    constraints = member_constraints(group, snapshot.members)
    feasibility = FeasibilityService(routing)
    for experience in experiences_by_id.values():
        verdict = await feasibility.evaluate(experience, constraints, travel_profile=group.travel_mode)
        if verdict.status != "FEASIBLE" or not real_schedule_evidence(group, experience, party_size):
            raise ApiError(
                "A selected activity no longer satisfies the group's verified budget, access, opening-hours, availability, or capacity constraints",
                status_code=409,
            )

    composition = await ExperienceComposerService(settings, routing).compose(
        candidates=ranked_candidates,
        itinerary_date=group.itinerary_date,
        start_time_of_day=group.start_time,
        end_time_of_day=group.end_time,
        max_experiences=len(required_items),
        max_budget=max_budget,
        travel_mode=group.travel_mode,
        origin_lat=group.origin_latitude,
        origin_lng=group.origin_longitude,
    )
    requested_ids = {item.experience_id for item in required_items}
    composed_ids = {item.experience.id for item in composition.items}
    if not composition.items or composed_ids != requested_ids:
        raise ApiError(
            "The selected required activities do not all fit a valid itinerary. Adjust the plan or time window and try again.",
            status_code=422,
        )

    requested_start = datetime.combine(group.itinerary_date, group.start_time, tzinfo=_GROUP_TZ)
    requested_end = datetime.combine(group.itinerary_date, group.end_time, tzinfo=_GROUP_TZ)
    validation = await ItineraryValidatorService(routing).validate(
        items=composition.items,
        experiences_by_id=experiences_by_id,
        requested_start=requested_start,
        requested_end=requested_end,
        max_budget=max_budget,
        max_experiences=len(required_items),
        party_size=party_size,
        travel_mode=group.travel_mode,
    )
    if not validation.valid:
        raise ApiError("The existing itinerary validator rejected the group schedule", status_code=422)

    for item in composition.items:
        experience = experiences_by_id[item.experience.id]
        precise_constraints = TravelerConstraints(
            **{
                **constraints.model_dump(),
                "available_date": item.planned_start.date(),
                "available_start": item.planned_start.time(),
                "available_end": item.planned_end.time(),
            }
        )
        verdict = await feasibility.evaluate(experience, precise_constraints, travel_profile=group.travel_mode)
        if (
            verdict.status != "FEASIBLE"
            or not real_schedule_evidence(
                group,
                experience,
                party_size,
                visit_start=item.planned_start,
                visit_end=item.planned_end,
            )
        ):
            raise ApiError("A scheduled activity lacks verified real availability or opening-hour evidence", status_code=422)

    narration = await ItineraryNarratorService(ai, settings).narrate(
        items=composition.items,
        itinerary_date_str=group.itinerary_date.isoformat(),
        currency="INR",
        total_cost=composition.estimated_total_cost or 0.0,
        booking_statuses={},
    )
    narrative_by_id = {item.experience_id: item.text for item in narration.narrative.item_narratives}
    itineraries: list[Itinerary] = []
    for member in snapshot.members:
        traveler = await session.scalar(select(Traveler).where(Traveler.user_id == member.user_id))
        if traveler is None:
            raise ApiError("A group member has no traveler profile for Trips integration", status_code=409)
        itinerary = Itinerary(
            traveler_id=traveler.id,
            title=narration.narrative.title,
            itinerary_date=group.itinerary_date,
            start_time=group.start_time,
            end_time=group.end_time,
            status="VALIDATED",
            source="COMPOSER",
            total_duration_minutes=composition.total_duration_minutes,
            total_travel_minutes=composition.total_travel_minutes,
            estimated_total_cost=composition.estimated_total_cost,
            currency="INR",
            narrative_title=narration.narrative.title,
            narrative_summary=narration.narrative.summary,
            narrative_closing_message=narration.narrative.closing_message,
            ranking_model_version=_COLLAB_RANKING_VERSION,
            narrative_model_version=narration.model_version,
            generated_at=datetime.now(_GROUP_TZ),
        )
        session.add(itinerary)
        await session.flush()
        for item in composition.items:
            session.add(
                ItineraryItem(
                    itinerary_id=itinerary.id,
                    experience_id=item.experience.id,
                    sequence_order=item.sequence_order,
                    planned_start=item.planned_start,
                    planned_end=item.planned_end,
                    duration_minutes=item.duration_minutes,
                    travel_from_previous_minutes=item.travel_from_previous_minutes,
                    travel_from_previous_distance_km=item.travel_from_previous_distance_km,
                    travel_mode=item.travel_mode,
                    buffer_before_minutes=item.buffer_before_minutes,
                    buffer_after_minutes=item.buffer_after_minutes,
                    estimated_cost=item.estimated_cost,
                    source_rank_position=item.source_rank_position,
                    source_ranking_score=item.source_ranking_score,
                    narrative_text=narrative_by_id.get(item.experience.id),
                )
            )
        session.add(
            CollabItineraryTrip(
                collab_itinerary_id=plan.id,
                user_id=member.user_id,
                itinerary_id=itinerary.id,
            )
        )
        itineraries.append(itinerary)

    plan.status = "FINALIZED"
    plan.version += 1
    await session.commit()
    for itinerary in itineraries:
        await session.refresh(itinerary)
    return itineraries


__all__ = ["finalize_collab_plan"]
