"""Orchestrates the full Phase 8 pipeline for one compose request:

RETRIEVAL -> FEASIBILITY -> RANKING -> COMPOSITION -> POST-COMPOSITION
VALIDATION -> NARRATIVE -> persist.

This module — not the route handler — owns the ordering invariant so it
can be reused identically by both POST /itineraries/compose and the
compose_experience Gemini tool (src/services/ai_tools.py), which must
never re-run the Phase 6/7 pipeline redundantly when a valid ranked
candidate context is already available (see execute_compose_experience).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import permutations

from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.embedding import EmbeddingAdapter
from src.adapters.routing import RoutingAdapter
from src.core.config import Settings
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.models.experience import Experience
from src.models.itinerary import Itinerary
from src.models.itinerary_custom_activity import ItineraryCustomActivity
from src.models.itinerary_item import ItineraryItem
from src.repositories.experience_repository import ExperienceRepository
from src.repositories.itinerary_repository import ItineraryRepository
from src.schemas.conversation import TravelerContext
from src.schemas.itinerary import ComposeItineraryRequest, ItineraryPreviewResponse
from src.schemas.ranking import RankedExperienceItem
from src.services.discovery_pipeline import DiscoveryPipelineService, PipelineItem
from src.services.experience_composer import ComposedItem, CompositionResult, ExperienceComposerService
from src.services.feasibility import FeasibilityService
from src.services.itinerary_narrator import ItineraryNarratorService
from src.services.itinerary_validator import ItineraryValidatorService, ValidationIssue

_DEFAULT_TZ = "Asia/Kolkata"
_MAX_AUTOMATIC_ORDER_STOPS = 7


@dataclass
class ComposeOutcome:
    valid: bool
    itinerary: Itinerary | None = None
    reason_code: str | None = None
    message: str | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    candidate_count: int = 0
    feasible_count: int = 0


async def _get_ranked_feasible_candidates(
    *,
    session: AsyncSession,
    settings: Settings,
    embedding_adapter: EmbeddingAdapter | None,
    routing_adapter: RoutingAdapter,
    traveler_id: str,
    request: ComposeItineraryRequest,
) -> tuple[list[RankedExperienceItem], int, int]:
    """Runs the Phase 6+7 pipeline exactly once and returns only FEASIBLE,
    ranked candidates. Returns (ranked_items, candidate_count, feasible_count)."""
    from src.schemas.feasibility import TravelerConstraints

    pipeline = DiscoveryPipelineService(session, settings, embedding_adapter, routing_adapter)
    # available_date is passed (filters out day-of-week closures), but
    # available_start/available_end are NOT: FeasibilityService's
    # opening-hours/availability checks require full CONTAINMENT of
    # whatever window is supplied (correct for verifying one specific
    # visit), and default an omitted start/end to the full 00:00-23:59
    # day — which would wrongly require every candidate to be open/
    # bookable across the traveler's *entire* day, when only whatever
    # specific slot the composer eventually schedules it into matters.
    # ItineraryValidatorService re-runs the full precise check against
    # each item's actual planned start/end after composition — that is
    # the mandatory, authoritative gate for per-slot time fit.
    constraints = TravelerConstraints(
        budget_max=request.max_budget,
        party_size=request.party_size,
        available_date=request.itinerary_date,
        origin_lat=request.origin_lat,
        origin_lng=request.origin_lng,
        travel_mode=request.travel_mode,
        accessibility_requirements=request.accessibility_requirements,
    )

    if request.experience_ids:
        # Selected IDs are canonical Experience rows, loaded from the same
        # repository and passed through the same deterministic feasibility
        # and personalization services. Missing or infeasible selections
        # fail as a whole; the composer never silently substitutes another
        # place or persists a partial selection.
        repository = ExperienceRepository(session)
        selected: list[Experience] = []
        for experience_id in request.experience_ids:
            experience = await repository.get_by_id(experience_id)
            if experience is not None:
                selected.append(experience)

        feasibility = FeasibilityService(routing_adapter)
        pipeline_items: list[PipelineItem] = []
        for experience in selected:
            verdict = await feasibility.evaluate(experience, constraints, travel_profile=request.travel_mode)
            if verdict.status == "FEASIBLE":
                pipeline_items.append(
                    PipelineItem(
                        experience_id=experience.id,
                        similarity=None,
                        verdict=verdict,
                        experience=experience,
                    )
                )

        if len(selected) != len(request.experience_ids) or len(pipeline_items) != len(request.experience_ids):
            return [], len(request.experience_ids), len(pipeline_items)

        from src.services.ranking import PersonalizedRankingService

        ranked = await PersonalizedRankingService(settings).rank(
            traveler_id=traveler_id,
            pipeline_items=pipeline_items,
            context=TravelerContext(
                raw_query=request.query or "",
                interests=request.interests,
                category_slugs=request.category_slugs,
                budget_max=request.max_budget,
            ),
            session=session,
        )
        requested_order = {experience_id: index for index, experience_id in enumerate(request.experience_ids)}
        ranked.sort(key=lambda item: requested_order.get(item.id, len(requested_order)))
        for index, item in enumerate(ranked, start=1):
            item.rank = index
        return ranked, len(request.experience_ids), len(pipeline_items)

    category_slug = request.category_slugs[0] if request.category_slugs else None
    result, ranked_items = await pipeline.run_with_ranking(
        traveler_id=traveler_id,
        raw_query=request.query,
        interests=request.interests or None,
        category_slug=category_slug,
        city=request.city,
        locality=request.locality,
        constraints=constraints,
        limit=settings.composer_max_candidates,
        travel_profile=request.travel_mode,
    )
    return ranked_items, result.candidate_count, result.feasible_count


async def _schedule_aware_selected_order(
    *,
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    request: ComposeItineraryRequest,
    candidates: list[RankedExperienceItem],
) -> list[RankedExperienceItem]:
    """Reorder a small explicit selection when its chosen order misses hours.

    Every place still has to pass the same date, hours, availability, budget,
    and travel checks. This only searches other orders of the exact selected
    IDs; it never drops or substitutes a stop.
    """
    ids = [candidate.id for candidate in candidates]
    if len(ids) < 2 or len(ids) > _MAX_AUTOMATIC_ORDER_STOPS:
        return candidates

    from src.services.itinerary_preview import preview_itinerary_plans

    orders = list(permutations(ids))
    previews = await preview_itinerary_plans(
        session=session,
        settings=settings,
        routing_adapter=routing_adapter,
        base=request,
        plans=[list(order) for order in orders],
    )
    feasible_orders = [
        (order, preview)
        for order, preview in zip(orders, previews, strict=True)
        if preview.valid
    ]
    if not feasible_orders:
        return candidates

    original_order = tuple(ids)
    if any(order == original_order for order, _ in feasible_orders):
        return candidates

    original_positions = {experience_id: index for index, experience_id in enumerate(ids)}

    def route_score(
        entry: tuple[tuple[str, ...], ItineraryPreviewResponse],
    ) -> tuple[float, float, tuple[int, ...]]:
        order, preview = entry
        route_distance = sum(
            item.travel_from_previous_distance_km or 0
            for item in preview.items[1:]
        )
        duration = preview.total_minutes if preview.total_minutes is not None else float("inf")
        return duration, route_distance, tuple(original_positions[item] for item in order)

    best_order, _ = min(feasible_orders, key=route_score)
    by_id = {candidate.id: candidate for candidate in candidates}
    ordered_candidates = [by_id[experience_id] for experience_id in best_order]
    # ExperienceComposerService sorts candidates by rank, so update rank as
    # well as list order to ensure the selected feasible sequence is honored.
    for rank, candidate in enumerate(ordered_candidates, start=1):
        candidate.rank = rank
    return ordered_candidates


async def compose_and_persist_itinerary(
    *,
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    embedding_adapter: EmbeddingAdapter | None,
    ai_adapter: AIAdapter,
    traveler_id: str,
    request: ComposeItineraryRequest,
    ranked_candidates: list[RankedExperienceItem] | None = None,
) -> ComposeOutcome:
    custom_only_request = bool(request.custom_activities) and not request.experience_ids and not request.query
    if ranked_candidates is None and custom_only_request:
        ranked_candidates, candidate_count, feasible_count = [], 0, 0
    elif ranked_candidates is None:
        ranked_candidates, candidate_count, feasible_count = await _get_ranked_feasible_candidates(
            session=session,
            settings=settings,
            embedding_adapter=embedding_adapter,
            routing_adapter=routing_adapter,
            traveler_id=traveler_id,
            request=request,
        )
    else:
        candidate_count = len(ranked_candidates)
        feasible_count = len(ranked_candidates)

    if not ranked_candidates and not custom_only_request:
        return ComposeOutcome(
            valid=False,
            reason_code="COMPOSITION_NO_VALID_PLAN",
            message="No feasible experiences were found for the given constraints.",
            candidate_count=candidate_count,
            feasible_count=feasible_count,
        )

    if request.experience_ids and len(ranked_candidates) == len(request.experience_ids):
        ranked_candidates = await _schedule_aware_selected_order(
            session=session,
            settings=settings,
            routing_adapter=routing_adapter,
            request=request,
            candidates=ranked_candidates,
        )

    composer = ExperienceComposerService(settings, routing_adapter)
    exp_repo = ExperienceRepository(session)
    validator = ItineraryValidatorService(routing_adapter)
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(_DEFAULT_TZ)
    requested_start = datetime.combine(request.itinerary_date, request.start_time, tzinfo=tz)
    requested_end = datetime.combine(request.itinerary_date, request.end_time, tzinfo=tz)

    # The composer's greedy/local-improvement stages check time window,
    # travel time, and budget, but not a candidate's precise opening-hours
    # /availability fit at its specific proposed slot (that data isn't on
    # the flat RankedExperienceItem candidates it works from). The
    # mandatory post-composition validator re-checks each item against
    # real Experience data at its actual planned start/end and is the
    # authoritative, precise gate. When it rejects a specific item as no
    # longer feasible at its assigned slot, exclude that one experience
    # and recompose from the remaining pool — bounded, deterministic,
    # never silently accepting an invalid plan (docs Section 20 step 20).
    excluded_ids: set[str] = set()
    composition: CompositionResult | None = None
    validation = None
    attempts = 0
    max_attempts = max(1, settings.composer_max_validation_retries)

    while ranked_candidates and attempts < max_attempts:
        attempts += 1
        pool = [c for c in ranked_candidates if c.id not in excluded_ids]
        if not pool:
            break

        composition = await composer.compose(
            candidates=pool,
            itinerary_date=request.itinerary_date,
            start_time_of_day=request.start_time,
            end_time_of_day=request.end_time,
            max_experiences=request.max_experiences,
            max_budget=request.max_budget,
            travel_mode=request.travel_mode,
            origin_lat=request.origin_lat,
            origin_lng=request.origin_lng,
            pace=request.pace,
        )

        if not composition.items:
            break

        if request.experience_ids and {item.experience.id for item in composition.items} != set(request.experience_ids):
            return ComposeOutcome(
                valid=False,
                reason_code="COMPOSITION_NO_VALID_PLAN",
                message=(
                    "The selected places could not all fit this time, travel, and budget plan. "
                    "Adjust the constraints or selected places and try again."
                ),
                candidate_count=candidate_count,
                feasible_count=feasible_count,
            )

        experiences_by_id = {}
        for item in composition.items:
            exp = await exp_repo.get_by_id(item.experience.id)
            if exp is not None:
                experiences_by_id[item.experience.id] = exp

        validation = await validator.validate(
            items=composition.items,
            experiences_by_id=experiences_by_id,
            requested_start=requested_start,
            requested_end=requested_end,
            max_budget=request.max_budget,
            max_experiences=request.max_experiences,
            party_size=request.party_size,
            travel_mode=request.travel_mode,
        )

        if validation.valid:
            break

        newly_excluded = {
            str(issue.evidence["experience_id"])
            for issue in validation.issues
            if issue.code == FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE and "experience_id" in issue.evidence
        }
        if not newly_excluded or newly_excluded <= excluded_ids:
            # Nothing new to exclude (a non-per-item issue, e.g. budget/
            # count) — retrying with the same pool would repeat forever.
            break
        excluded_ids |= newly_excluded

    if composition is None or not composition.items:
        if custom_only_request and not ranked_candidates:
            composition = CompositionResult()
        else:
            return ComposeOutcome(
                valid=False,
                reason_code="COMPOSITION_NO_VALID_PLAN",
                message="No combination of feasible experiences fit the requested time window and constraints.",
                candidate_count=candidate_count,
                feasible_count=feasible_count,
            )

    if composition.items and (validation is None or not validation.valid):
        return ComposeOutcome(
            valid=False,
            reason_code="COMPOSITION_NO_VALID_PLAN",
            message="The composed itinerary failed validation.",
            issues=validation.issues if validation else [],
            candidate_count=candidate_count,
            feasible_count=feasible_count,
        )

    custom_issues = _validate_custom_activities(request, composition, settings)
    if custom_issues:
        return ComposeOutcome(
            valid=False,
            reason_code="COMPOSITION_NO_VALID_PLAN",
            message="One or more personal activities conflict with the checked itinerary.",
            issues=custom_issues,
            candidate_count=candidate_count,
            feasible_count=feasible_count,
        )

    if composition.items:
        narrator = ItineraryNarratorService(ai_adapter, settings)
        outcome_narration = await narrator.narrate(
            items=composition.items,
            itinerary_date_str=request.itinerary_date.isoformat(),
            currency="INR",
            total_cost=composition.estimated_total_cost,
            booking_statuses={},
        )
        narrative_title = outcome_narration.narrative.title
        narrative_summary = outcome_narration.narrative.summary
        narrative_closing_message = outcome_narration.narrative.closing_message
        narrative_model_version = outcome_narration.model_version
        narrative_by_id = {n.experience_id: n.text for n in outcome_narration.narrative.item_narratives}
    else:
        narrative_title = f"Your plan for {request.itinerary_date.isoformat()}"
        narrative_summary = "Your personal activities are saved in the timeline below."
        narrative_closing_message = "Check travel to and from personal stops before you go."
        narrative_model_version = "traveler-authored-v1"
        narrative_by_id = {}

    custom_costs_known = all(activity.estimated_cost is not None for activity in request.custom_activities)
    catalog_costs_known = all(item.estimated_cost is not None for item in composition.items)
    total_cost = (
        sum(item.estimated_cost or 0.0 for item in composition.items)
        + sum(activity.estimated_cost or 0.0 for activity in request.custom_activities)
    )
    has_physical_custom = any(
        activity.kind in ("place", "activity") and activity.duration_minutes > 0
        for activity in request.custom_activities
    )

    itinerary = Itinerary(
        traveler_id=traveler_id,
        title=narrative_title,
        itinerary_date=request.itinerary_date,
        start_time=request.start_time,
        end_time=request.end_time,
        status="VALIDATED",
        source="COMPOSER",
        total_duration_minutes=composition.total_duration_minutes
        + sum(activity.duration_minutes for activity in request.custom_activities),
        total_travel_minutes=None if has_physical_custom else composition.total_travel_minutes,
        estimated_total_cost=total_cost if custom_costs_known and catalog_costs_known else None,
        max_budget=request.max_budget,
        currency="INR",
        narrative_title=narrative_title,
        narrative_summary=narrative_summary,
        narrative_closing_message=narrative_closing_message,
        ranking_model_version=settings.ranking_model_version,
        narrative_model_version=narrative_model_version,
        generated_at=datetime.now(tz),
    )
    ItineraryRepository(session).add(itinerary)
    await session.flush()

    for composed in composition.items:
        item_row = ItineraryItem(
            itinerary_id=itinerary.id,
            experience_id=composed.experience.id,
            sequence_order=composed.sequence_order,
            planned_start=composed.planned_start,
            planned_end=composed.planned_end,
            duration_minutes=composed.duration_minutes,
            travel_from_previous_minutes=composed.travel_from_previous_minutes,
            travel_from_previous_distance_km=composed.travel_from_previous_distance_km,
            travel_mode=composed.travel_mode,
            buffer_before_minutes=composed.buffer_before_minutes,
            buffer_after_minutes=composed.buffer_after_minutes,
            estimated_cost=composed.estimated_cost,
            source_rank_position=composed.source_rank_position,
            source_ranking_score=composed.source_ranking_score,
            narrative_text=narrative_by_id.get(composed.experience.id),
        )
        session.add(item_row)

    for index, activity in enumerate(request.custom_activities, start=1):
        activity_start = datetime.combine(request.itinerary_date, activity.start_time, tzinfo=tz)
        session.add(ItineraryCustomActivity(
            itinerary_id=itinerary.id,
            sequence_order=len(composition.items) + index,
            title=activity.title,
            kind=activity.kind,
            note=activity.note,
            location_text=activity.location_text,
            latitude=activity.latitude,
            longitude=activity.longitude,
            planned_start=activity_start,
            planned_end=activity_start + timedelta(minutes=activity.duration_minutes),
            duration_minutes=activity.duration_minutes,
            estimated_cost=activity.estimated_cost,
        ))

    await session.commit()
    await session.refresh(itinerary, attribute_names=["items", "custom_activities"])

    return ComposeOutcome(
        valid=True,
        itinerary=itinerary,
        candidate_count=candidate_count,
        feasible_count=feasible_count,
    )


def _validate_custom_activities(
    request: ComposeItineraryRequest,
    composition: CompositionResult,
    settings: Settings,
) -> list[ValidationIssue]:
    from zoneinfo import ZoneInfo

    issues: list[ValidationIssue] = []
    tz = ZoneInfo(_DEFAULT_TZ)
    custom_intervals: list[tuple[datetime, datetime, str]] = []
    for activity in request.custom_activities:
        start = datetime.combine(request.itinerary_date, activity.start_time, tzinfo=tz)
        end = start + timedelta(minutes=activity.duration_minutes)
        if activity.duration_minutes == 0 or activity.kind == "note":
            continue
        for item in composition.items:
            if start < item.planned_end and item.planned_start < end:
                issues.append(ValidationIssue(
                    code=FeasibilityReasonCode.CUSTOM_ACTIVITY_CONFLICT,
                    constraint="schedule",
                    message=f"{activity.title} overlaps {item.experience.title}.",
                    evidence={"title": activity.title, "experience_id": item.experience.id},
                ))
        custom_intervals.append((start, end, activity.title))

    custom_intervals.sort(key=lambda value: value[0])
    for previous, current in zip(custom_intervals, custom_intervals[1:], strict=True):
        if current[0] < previous[1]:
            issues.append(ValidationIssue(
                code=FeasibilityReasonCode.CUSTOM_ACTIVITY_CONFLICT,
                constraint="schedule",
                message=f"{current[2]} overlaps {previous[2]}.",
                evidence={"first_title": previous[2], "second_title": current[2]},
            ))

    if request.max_budget is not None:
        prices = [item.estimated_cost for item in composition.items]
        prices.extend(activity.estimated_cost for activity in request.custom_activities)
        if any(price is None for price in prices):
            issues.append(ValidationIssue(
                code=FeasibilityReasonCode.PRICE_UNAVAILABLE,
                constraint="budget",
                message="The budget cannot be checked because a stop has no price.",
            ))
        else:
            total = sum(float(price) for price in prices if price is not None)
            if total > request.max_budget:
                issues.append(ValidationIssue(
                    code=FeasibilityReasonCode.ITINERARY_BUDGET_EXCEEDED,
                    constraint="budget",
                    message=f"The total cost {total:.0f} exceeds budget {request.max_budget:.0f}.",
                    evidence={"total_cost": total, "max_budget": request.max_budget},
                ))
    return issues


def _ranked_stub_for_validation(
    *, experience: Experience, sequence_order: int, ranking_model_version: str
) -> RankedExperienceItem:
    """Builds the minimal RankedExperienceItem shape ItineraryValidatorService
    needs (it only reads .id/.title/.category via ComposedItem.experience,
    plus what the composer already computed) from a canonical Experience row
    that was NOT part of a Phase 7 ranked candidate set (manual add path).
    ranking_score/semantic_relevance are 0.0 — this is never fed back into
    the composer's aggregate-score objective, only used for schedule
    display and re-validation."""
    return RankedExperienceItem.model_validate(
        {
            "id": experience.id,
            "title": experience.title,
            "short_description": experience.short_description,
            "category": experience.category,
            "location": experience.location,
            "provider": experience.provider,
            "currency": experience.currency,
            "price": experience.price,
            "minimum_price": experience.minimum_price,
            "maximum_price": experience.maximum_price,
            "price_type": experience.price_type,
            "is_price_estimated": experience.is_price_estimated,
            "duration_minutes": experience.duration_minutes,
            "duration_is_estimated": experience.duration_is_estimated,
            "status": experience.status,
            "verification_status": experience.verification_status,
            "is_synthetic": experience.is_synthetic,
            "is_enriched": experience.is_enriched,
            "rank": sequence_order,
            "ranking_score": 0.0,
            "ranking_model_version": ranking_model_version,
            "semantic_relevance": 0.0,
            "personalized": False,
        },
        from_attributes=True,
    )


async def add_item_to_itinerary(
    *,
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    itinerary: Itinerary,
    experience_id: str,
    planned_start: datetime | None,
    travel_mode: str,
) -> ComposeOutcome:
    """Adds one experience to an existing itinerary, re-running the
    validator over the full resulting item set before persisting — never
    appends without re-validation."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    exp_repo = ExperienceRepository(session)
    experience = await exp_repo.get_by_id(experience_id)
    if experience is None:
        return ComposeOutcome(valid=False, reason_code="ITINERARY_NOT_FOUND", message="Experience not found.")
    if experience.duration_minutes is None:
        return ComposeOutcome(
            valid=False,
            reason_code="COMPOSITION_NO_VALID_PLAN",
            message="Experience has no known duration; cannot schedule it.",
        )

    tz = ZoneInfo(_DEFAULT_TZ)
    ranking_model_version = itinerary.ranking_model_version or "weighted-v1"
    existing_items = sorted(itinerary.items, key=lambda i: i.sequence_order)
    if planned_start is None:
        planned_start = (
            existing_items[-1].planned_end
            if existing_items
            else datetime.combine(itinerary.itinerary_date, itinerary.start_time, tzinfo=tz)
        )
    planned_end = planned_start + timedelta(minutes=experience.duration_minutes)

    experiences_by_id = {experience.id: experience}
    composed_existing: list[ComposedItem] = []
    for item in existing_items:
        loaded = await exp_repo.get_by_id(item.experience_id)
        if loaded is not None:
            experiences_by_id[item.experience_id] = loaded
            composed_existing.append(
                ComposedItem(
                    experience=_ranked_stub_for_validation(
                        experience=loaded, sequence_order=item.sequence_order,
                        ranking_model_version=ranking_model_version,
                    ),
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
                    source_rank_position=item.source_rank_position or 0,
                    source_ranking_score=item.source_ranking_score or 0.0,
                )
            )

    price = experience.price if experience.price is not None else experience.maximum_price
    new_sequence = len(existing_items) + 1
    new_composed = ComposedItem(
        experience=_ranked_stub_for_validation(
            experience=experience, sequence_order=new_sequence, ranking_model_version=ranking_model_version
        ),
        sequence_order=new_sequence,
        planned_start=planned_start,
        planned_end=planned_end,
        duration_minutes=experience.duration_minutes,
        travel_from_previous_minutes=None,
        travel_from_previous_distance_km=None,
        travel_mode=travel_mode,
        buffer_before_minutes=settings.composer_min_buffer_minutes,
        buffer_after_minutes=0,
        estimated_cost=price,
        source_rank_position=None,
        source_ranking_score=None,
    )

    validator = ItineraryValidatorService(routing_adapter)
    requested_start = datetime.combine(itinerary.itinerary_date, itinerary.start_time, tzinfo=tz)
    requested_end = datetime.combine(itinerary.itinerary_date, itinerary.end_time, tzinfo=tz)
    validation = await validator.validate(
        items=composed_existing + [new_composed],
        experiences_by_id=experiences_by_id,
        requested_start=requested_start,
        requested_end=requested_end,
        max_budget=None,
        max_experiences=None,
        party_size=None,
        travel_mode=travel_mode,
    )
    if not validation.valid:
        return ComposeOutcome(valid=False, reason_code="COMPOSITION_TIME_CONFLICT", issues=validation.issues)

    new_item = ItineraryItem(
        itinerary_id=itinerary.id,
        experience_id=experience.id,
        sequence_order=new_sequence,
        planned_start=planned_start,
        planned_end=planned_end,
        duration_minutes=experience.duration_minutes,
        travel_from_previous_minutes=None,
        travel_from_previous_distance_km=None,
        travel_mode=travel_mode,
        buffer_before_minutes=settings.composer_min_buffer_minutes,
        buffer_after_minutes=0,
        estimated_cost=price,
        source_rank_position=None,
        source_ranking_score=None,
    )
    session.add(new_item)
    await session.commit()
    await session.refresh(itinerary, attribute_names=["items"])
    return ComposeOutcome(valid=True, itinerary=itinerary)


__all__ = ["ComposeOutcome", "add_item_to_itinerary", "compose_and_persist_itinerary"]
