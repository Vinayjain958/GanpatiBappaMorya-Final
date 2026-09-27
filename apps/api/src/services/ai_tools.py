"""Gemini tools: `search_experiences` (Phase 5) and `check_feasibility`
(Phase 6) — see docs/AI_CONTEXT.md and docs/DECISIONS.md ADR-034/ADR-044.

Each `*_DECLARATION` dict is the single source of truth for that tool's
schema, shared by the adapter (Live token `live_connect_constraints`
locking) and the tool-execution route — declared once, never duplicated.

`execute_search_experiences` is the ONLY implementation of the search
tool: a thin wrapper around the Phase 4 ExperienceDiscoveryService — its
argument schema carries no hard constraints (budget/time/capacity/etc.),
so it is deliberately unchanged in Phase 6. Feasibility verification for
a specific candidate is a separate, explicit second tool call
(check_feasibility) — this keeps "find candidates" and "verify this one
candidate" as two clearly separated steps for the model to reason about,
matching the target pipeline (retrieval -> feasibility, not conflated).

`execute_check_feasibility` is the ONLY implementation of the feasibility
tool. It loads the REAL experience from the database by experience_id and
runs the same FeasibilityService used by POST /api/v1/feasibility/check —
Gemini supplies only an experience_id and constraint context; it can
never inject a fabricated price/hours/capacity value, because
CheckFeasibilityArgs has no such fields and FeasibilityService only ever
reads them from the loaded Experience row.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.errors import AdapterError
from src.adapters.routing import RoutingAdapter
from src.adapters.weather import WeatherAdapter
from src.core.category_map import CATEGORY_SLUGS
from src.core.config import Settings
from src.core.digital_twin import get_domain_intelligence_provider
from src.core.errors import ApiError
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.conversation import (
    CheckFeasibilityArgs,
    ComposeExperienceArgs,
    ReplanExperienceArgs,
    SearchExperiencesArgs,
    SearchExperiencesResult,
    SimulateWhatIfArgs,
    TravelerContext,
)
from src.schemas.experience import ExperienceSummary
from src.schemas.feasibility import FeasibilityVerdict, TravelerConstraints
from src.schemas.itinerary import ComposeItineraryRequest, ItineraryResponse
from src.schemas.ranking import RankedExperienceItem
from src.services.digital_twin import DigitalTwinService
from src.services.discovery_pipeline import DiscoveryPipelineService
from src.services.feasibility import FeasibilityService
from src.services.social_signals import SocialSignalService

SEARCH_EXPERIENCES_DECLARATION: dict[str, object] = {
    "name": "search_experiences",
    "description": (
        "Search LocaLens's real catalog of local experiences. Returns only "
        "actual catalog records — never invent an experience that this "
        "tool did not return. Call this once enough information is known "
        "(e.g. an interest or location) rather than repeatedly asking the "
        "user for details that are not required."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "q": {"type": "STRING", "description": "Free-text keyword search (interest, food type, activity)."},
            "category_slug": {"type": "STRING", "description": "A LocaLens category slug, if confidently known."},
            "city": {"type": "STRING"},
            "locality": {"type": "STRING", "description": "Neighborhood/area name, e.g. 'Fort', 'Bandra'."},
            "min_price": {"type": "NUMBER"},
            "max_price": {"type": "NUMBER"},
            "min_duration_minutes": {"type": "INTEGER"},
            "max_duration_minutes": {"type": "INTEGER"},
            "sort": {
                "type": "STRING",
                "enum": ["relevance", "distance", "price", "duration", "newest"],
            },
            "limit": {"type": "INTEGER", "description": "Max results, 1-10. Defaults to 5."},
        },
    },
}


async def execute_search_experiences(
    session: AsyncSession,
    settings: Settings,
    args: SearchExperiencesArgs,
    traveler_id: str | None = None,
    context: TravelerContext | None = None,
    routing_adapter: RoutingAdapter | None = None,
    embedding_adapter: Any | None = None,
) -> SearchExperiencesResult:
    result, _ranked = await execute_search_experiences_with_candidates(
        session, settings, args,
        traveler_id=traveler_id, context=context,
        routing_adapter=routing_adapter, embedding_adapter=embedding_adapter,
    )
    return result


async def execute_search_experiences_with_candidates(
    session: AsyncSession,
    settings: Settings,
    args: SearchExperiencesArgs,
    traveler_id: str | None = None,
    context: TravelerContext | None = None,
    routing_adapter: RoutingAdapter | None = None,
    embedding_adapter: Any | None = None,
) -> tuple[SearchExperiencesResult, list[RankedExperienceItem] | None]:
    """Same execution as execute_search_experiences, but also returns the
    ranked FEASIBLE candidate list (None for anonymous callers, who never
    get ranking) — used by the conversation route to persist the
    compose_experience candidate context (ConversationSession.
    last_search_candidates). Both functions run the pipeline exactly once;
    execute_search_experiences is a thin wrapper over this one so there is
    only ever one real execution path."""
    category_slug = args.category_slug if args.category_slug in CATEGORY_SLUGS else None

    # Fallbacks in case adapters aren't injected here yet. Both provider
    # functions are process-wide lru_cache singletons that read settings
    # via get_settings() internally — they take no arguments.
    if not routing_adapter:
        from src.core.location import get_routing_adapter
        routing_adapter = get_routing_adapter()

    if not embedding_adapter:
        from src.core.embedding import get_embedding_adapter
        embedding_adapter = get_embedding_adapter()

    pipeline = DiscoveryPipelineService(session, settings, embedding_adapter, routing_adapter)

    constraints = TravelerConstraints(
        budget_max=args.max_price,
        budget_min=args.min_price,
    )
    if args.max_duration_minutes:
        constraints.available_duration_minutes = args.max_duration_minutes

    ranked_items: list[RankedExperienceItem] | None = None
    summaries: list[ExperienceSummary]
    if traveler_id:
        result, ranked_items = await pipeline.run_with_ranking(
            traveler_id=traveler_id,
            raw_query=args.q,
            category_slug=category_slug,
            city=args.city,
            locality=args.locality,
            constraints=constraints,
            limit=args.limit,
            context=context,
        )
        summaries = list(ranked_items)
        total = result.candidate_count
    else:
        result = await pipeline.run(
            raw_query=args.q,
            category_slug=category_slug,
            city=args.city,
            locality=args.locality,
            constraints=constraints,
            limit=args.limit,
        )
        # Use PipelineItem experiences
        summaries = [ExperienceSummary.model_validate(item.experience) for item in result.items]
        total = result.candidate_count

    search_result = SearchExperiencesResult(items=summaries, total=total, truncated=total > len(summaries))
    return search_result, ranked_items


CHECK_FEASIBILITY_DECLARATION: dict[str, object] = {
    "name": "check_feasibility",
    "description": (
        "Deterministically verify whether a specific LocaLens catalog "
        "experience is feasible given traveler constraints (budget, "
        "available time, party size, travel time/distance, accessibility). "
        "This is NOT an LLM judgment — it queries real stored data and "
        "returns FEASIBLE, INFEASIBLE, or UNKNOWN with explicit reasons. "
        "Only call this with an experience_id previously returned by "
        "search_experiences. Never invent a price, opening hours, "
        "capacity, or availability value yourself — this tool is the only "
        "source of truth for feasibility. If the result is UNKNOWN, tell "
        "the traveler the information isn't available — never say it is "
        "'probably okay'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "experience_id": {"type": "STRING", "description": "An experience id from search_experiences results."},
            "budget_max": {"type": "NUMBER"},
            "available_duration_minutes": {"type": "INTEGER"},
            "party_size": {"type": "INTEGER"},
            "max_travel_time_minutes": {"type": "NUMBER"},
            "max_distance_km": {"type": "NUMBER"},
            "origin_lat": {"type": "NUMBER"},
            "origin_lng": {"type": "NUMBER"},
            "accessibility_requirements": {
                "type": "ARRAY",
                "items": {"type": "STRING", "enum": ["wheelchair_accessible", "step_free"]},
            },
        },
        "required": ["experience_id"],
    },
}


async def execute_check_feasibility(
    session: AsyncSession,
    routing_adapter: RoutingAdapter,
    settings: Settings,
    args: CheckFeasibilityArgs,
) -> FeasibilityVerdict:
    experience = await ExperienceRepository(session).get_by_id(args.experience_id)
    if experience is None:
        raise ApiError(f"Experience '{args.experience_id}' not found", status_code=404)

    constraints = TravelerConstraints(
        budget_max=args.budget_max,
        available_duration_minutes=args.available_duration_minutes,
        party_size=args.party_size,
        max_travel_time_minutes=args.max_travel_time_minutes,
        max_distance_km=args.max_distance_km,
        origin_lat=args.origin_lat,
        origin_lng=args.origin_lng,
        accessibility_requirements=args.accessibility_requirements,
    )
    service = FeasibilityService(routing_adapter)
    return await service.evaluate(experience, constraints, travel_profile=settings.osrm_profile)


COMPOSE_EXPERIENCE_DECLARATION: dict[str, object] = {
    "name": "compose_experience",
    "description": (
        "Compose a chronological, travel-aware itinerary from experiences "
        "already returned by search_experiences in this conversation. "
        "Never call this with an experience_id that search_experiences did "
        "not just return. This tool deterministically decides ordering, "
        "timing, travel gaps, and feasibility — you (the model) never "
        "invent or override any of that; only narrate the validated result "
        "it returns. If composition fails, tell the traveler honestly "
        "that no valid plan could be built for their constraints — never "
        "present a partial or guessed itinerary as final."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "experience_ids": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Experience ids from the most recent search_experiences result to consider.",
            },
            "itinerary_date": {"type": "STRING", "description": "YYYY-MM-DD"},
            "start_time": {"type": "STRING", "description": "HH:MM, 24-hour"},
            "end_time": {"type": "STRING", "description": "HH:MM, 24-hour"},
            "max_experiences": {"type": "INTEGER"},
            "max_budget": {"type": "NUMBER"},
            "pace": {"type": "STRING", "enum": ["relaxed", "balanced", "packed"]},
            "must_include_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            "exclude_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["itinerary_date", "start_time", "end_time"],
    },
}


async def execute_compose_experience(
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    embedding_adapter: Any,
    ai_adapter: Any,
    args: ComposeExperienceArgs,
    traveler_id: str,
    candidate_context: list[dict[str, object]] | None,
) -> ItineraryResponse | dict[str, object]:
    """The ONLY implementation of the compose_experience tool.

    traveler_id is always server-derived by the caller (conversation.py)
    — never accepted as a tool argument. experience_ids Gemini supplies
    are validated against `candidate_context`
    (ConversationSession.last_search_candidates, populated by the most
    recent search_experiences call in this conversation) — an id not
    present there is silently dropped, never trusted blindly. If no
    candidate context exists yet, this function runs exactly one fresh
    Phase 6+7 pipeline pass (never a redundant second pass when a context
    already exists).
    """
    from src.services.compose_itinerary import compose_and_persist_itinerary

    ranked_candidates: list[RankedExperienceItem] | None = None
    if candidate_context:
        allowed_ids = set(args.experience_ids) or None
        ranked_candidates = [
            RankedExperienceItem.model_validate(c)
            for c in candidate_context
            if allowed_ids is None or c.get("id") in allowed_ids
        ]

    if candidate_context is not None and args.exclude_ids:
        exclude = set(args.exclude_ids)
        ranked_candidates = [c for c in (ranked_candidates or []) if c.id not in exclude]

    request = ComposeItineraryRequest(
        itinerary_date=args.itinerary_date,
        start_time=args.start_time,
        end_time=args.end_time,
        max_experiences=args.max_experiences,
        max_budget=args.max_budget,
        pace=args.pace,
    )

    outcome = await compose_and_persist_itinerary(
        session=session,
        settings=settings,
        routing_adapter=routing_adapter,
        embedding_adapter=embedding_adapter,
        ai_adapter=ai_adapter,
        traveler_id=traveler_id,
        request=request,
        # Only pass a pre-built candidate list when we actually have one —
        # None triggers exactly one fresh Phase 6+7 pipeline run inside
        # compose_and_persist_itinerary, never a redundant extra pass when
        # a context already exists.
        ranked_candidates=ranked_candidates if candidate_context else None,
    )

    if not outcome.valid or outcome.itinerary is None:
        return {
            "valid": False,
            "reason_code": outcome.reason_code or "COMPOSITION_NO_VALID_PLAN",
            "message": outcome.message or "No valid itinerary could be composed for the given constraints.",
            "issues": [
                {"code": i.code.value, "constraint": i.constraint, "message": i.message} for i in outcome.issues
            ],
        }

    from src.api.v1.itineraries import _to_itinerary_response

    return await _to_itinerary_response(outcome.itinerary, session)


REPLAN_EXPERIENCE_DECLARATION: dict[str, object] = {
    "name": "replan_experience",
    "description": (
        "Request the backend to re-plan part of an existing, already-"
        "composed itinerary — e.g. because the traveler wants to change "
        "the time, budget, or party size, or wants a specific experience "
        "swapped out. This tool NEVER directly edits the itinerary: it "
        "only asks the backend's deterministic ReplanningService to "
        "re-run retrieval, feasibility, ranking, composition, and "
        "validation for the affected part of the plan. You (the model) "
        "never decide feasibility, weather suitability, event "
        "cancellation, schedule conflicts, or itinerary validity — only "
        "narrate the structured result this tool returns. If the result "
        "status is REPLAN_FAILED or REQUIRES_USER_ACTION, tell the "
        "traveler honestly what happened; never claim the plan changed "
        "when it didn't, and never claim a booking is confirmed."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "itinerary_id": {"type": "STRING", "description": "The itinerary to replan."},
            "affected_experience_id": {
                "type": "STRING",
                "description": (
                    "Hint only — the experience the traveler wants changed, if any. Always revalidated server-side."
                ),
            },
            "requested_change": {
                "type": "STRING",
                "description": "A short description of what the traveler wants changed.",
            },
            "new_start_time": {
                "type": "STRING",
                "description": "HH:MM, 24-hour, if the traveler wants a new start time.",
            },
            "new_end_time": {"type": "STRING", "description": "HH:MM, 24-hour, if the traveler wants a new end time."},
            "new_max_budget": {"type": "NUMBER"},
            "new_party_size": {"type": "INTEGER"},
        },
        "required": ["itinerary_id", "requested_change"],
    },
}


SIMULATE_WHAT_IF_DECLARATION: dict[str, object] = {
    "name": "simulate_what_if",
    "description": (
        "Create a read-only, short-lived what-if preview for one of the authenticated traveler's "
        "existing itineraries. This tool never applies or persists a changed plan. Use it only when "
        "the traveler asks to explore a hypothetical. Weather and social inputs are assumptions or "
        "advisory evidence; never describe them as verified facts, and never let this preview decide "
        "safety or feasibility."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "itinerary_id": {
                "type": "STRING",
                "description": "An itinerary identifier already known in this conversation.",
            },
            "scenario": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "include_recent_social_context": {"type": "BOOLEAN"},
                    "social_context_item_id": {"type": "STRING"},
                    "horizon_hours": {"type": "INTEGER", "minimum": 1, "maximum": 72},
                    "weather": {
                        "type": "OBJECT",
                        "properties": {
                            "intensity": {
                                "type": "STRING",
                                "enum": [
                                    "clear",
                                    "light_rain",
                                    "moderate_rain",
                                    "heavy_rain",
                                    "severe_rain",
                                    "high_temperature",
                                    "extreme_heat",
                                    "strong_wind",
                                    "poor_visibility",
                                ],
                            },
                            "starts_at": {"type": "STRING", "description": "Local trip time, HH:MM:SS."},
                            "ends_at": {"type": "STRING", "description": "Optional local trip time, HH:MM:SS."},
                        },
                    },
                    "route": {
                        "type": "OBJECT",
                        "properties": {
                            "kind": {
                                "type": "STRING",
                                "enum": ["road_disruption", "temporary_closure", "congestion", "walking_condition"],
                            },
                            "from_item_id": {"type": "STRING"},
                            "to_item_id": {"type": "STRING"},
                            "assumed_delay_minutes": {"type": "INTEGER", "minimum": 0, "maximum": 240},
                        },
                    },
                },
            },
        },
        "required": ["itinerary_id"],
    },
}


async def execute_simulate_what_if(
    *,
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    embedding_adapter: Any,
    weather_adapter: WeatherAdapter,
    social_service: SocialSignalService,
    args: SimulateWhatIfArgs,
    traveler_id: str,
) -> dict[str, object]:
    """Return a preview owned by the authenticated traveler; no itinerary writes occur."""
    service = DigitalTwinService(
        session=session,
        settings=settings,
        weather=weather_adapter,
        routing=routing_adapter,
        embedding=embedding_adapter,
        social=social_service,
        intelligence=get_domain_intelligence_provider(settings),
    )
    try:
        result = await service.simulate(
            itinerary_id=args.itinerary_id,
            traveler_id=traveler_id,
            scenario=args.scenario,
        )
    except LookupError as exc:
        raise ApiError("Itinerary not found", status_code=404) from exc
    except ValueError as exc:
        raise ApiError(str(exc), status_code=422) from exc
    except AdapterError as exc:
        raise ApiError(
            "Domain intelligence is temporarily unavailable. Retry the preview later.", status_code=503
        ) from exc
    return result.model_dump(mode="json")


async def execute_replan_experience(
    session: AsyncSession,
    settings: Settings,
    routing_adapter: RoutingAdapter,
    embedding_adapter: Any,
    ai_adapter: Any,
    args: ReplanExperienceArgs,
    traveler_id: str,
) -> dict[str, object]:
    """The ONLY implementation of the replan_experience tool. traveler_id
    is always server-derived by the caller — never a tool argument. This
    function never mutates the itinerary itself: it builds a
    USER_REQUESTED-trigger context impact covering every remaining
    flexible item (optionally hinting at affected_experience_id, which is
    only ever used to prioritize — never trusted blindly) and delegates
    entirely to ReplanningService, the same service the manual REST
    replan endpoint and ContextMonitor use — no second replanning path.
    """
    from src.repositories.itinerary_repository import ItineraryRepository
    from src.services.context_impact import ContextImpactResult, ImpactSeverity
    from src.services.replanning import ReplanningService

    itinerary_repo_result = await ItineraryRepository(session).get_owned_by_id(args.itinerary_id, traveler_id)
    if itinerary_repo_result is None:
        # Never disclose existence of another traveler's itinerary, even
        # to Gemini — same non-disclosure pattern as every REST route.
        return {
            "status": "CONFLICT",
            "reason_code": "ITINERARY_NOT_FOUND",
            "message": "Itinerary not found.",
        }

    from datetime import datetime as _datetime

    now = (
        _datetime.now(itinerary_repo_result.items[0].planned_start.tzinfo)
        if itinerary_repo_result.items
        else _datetime.now()
    )
    flexible_ids = [
        i.id for i in itinerary_repo_result.items
        if i.planned_end > now and not i.is_locked
    ]
    impact = ContextImpactResult(
        affected=bool(flexible_ids),
        severity=ImpactSeverity.MEDIUM if flexible_ids else ImpactSeverity.NONE,
        context_type="USER",
        affected_itinerary_item_ids=flexible_ids,
        reason_codes=["USER_REQUESTED"],
        explanation=args.requested_change,
    )

    service = ReplanningService(
        session=session,
        settings=settings,
        routing_adapter=routing_adapter,
        embedding_adapter=embedding_adapter,
        ai_adapter=ai_adapter,
    )
    outcome = await service.replan_itinerary(
        itinerary_id=args.itinerary_id,
        traveler_id=traveler_id,
        trigger="USER_REQUESTED",
        impact=impact,
        reason=args.requested_change,
    )

    return {
        "status": outcome.status,
        "itinerary_id": args.itinerary_id,
        "previous_version": outcome.previous_version,
        "new_version": outcome.new_version,
        "trigger": outcome.trigger,
        "changes": {
            "added_items": outcome.changes.added_items,
            "removed_items": outcome.changes.removed_items,
            "unchanged_items": outcome.changes.unchanged_items,
            "affected_items": outcome.changes.affected_items,
        },
        "context_summary": outcome.context_summary,
        "reason_code": outcome.reason_code,
        "message": outcome.message,
    }


__all__ = [
    "CHECK_FEASIBILITY_DECLARATION",
    "COMPOSE_EXPERIENCE_DECLARATION",
    "REPLAN_EXPERIENCE_DECLARATION",
    "SIMULATE_WHAT_IF_DECLARATION",
    "SEARCH_EXPERIENCES_DECLARATION",
    "execute_check_feasibility",
    "execute_compose_experience",
    "execute_replan_experience",
    "execute_simulate_what_if",
    "execute_search_experiences",
    "execute_search_experiences_with_candidates",
]
