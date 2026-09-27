"""Text-mode conversational-turn orchestration (Phase 5, extended Phase 6).

The assistant's reply text is a deterministic template, never a second
free-form Gemini call — one Gemini call per turn total (structured
TravelerContext extraction only). This guarantees the text path can never
fabricate commentary about results and keeps mock-mode behavior trivially
reproducible (docs/DECISIONS.md ADR-034).

Phase 6: when the extracted TravelerContext carries any hard constraint
(budget/time/party size/travel/accessibility), the turn routes through
DiscoveryPipelineService (semantic retrieval -> deterministic feasibility
gate) instead of the plain keyword ExperienceDiscoveryService, and the
templated reply text honestly reflects verified-feasible counts — still
no free-form LLM feasibility verdict on this path (docs/DECISIONS.md
ADR-043).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.embedding import EmbeddingAdapter
from src.adapters.routing import RoutingAdapter
from src.core.category_map import CATEGORY_SLUGS
from src.core.config import Settings
from src.models.conversation_message import ConversationMessage
from src.models.conversation_session import ConversationSession
from src.repositories.experience_repository import ExperienceRepository
from src.schemas.conversation import (
    ConversationTurnResponse,
    SearchExperiencesArgs,
    SearchExperiencesResult,
    TravelerContext,
)
from src.schemas.experience import ExperienceSummary
from src.schemas.feasibility import TravelerConstraints
from src.services.ai_tools import execute_search_experiences
from src.services.discovery_pipeline import DiscoveryPipelineService


async def _recent_history(session: AsyncSession, conversation_id: str, window: int) -> list[ConversationMessage]:
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.session_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(window)
    )
    result = await session.execute(stmt)
    return list(reversed(result.scalars().all()))


def _build_extraction_prompt(history: list[ConversationMessage], user_message: str) -> str:
    lines = [
        "You are LocaLens's discovery understanding step. Extract structured "
        "traveler intent from the conversation below as a TravelerContext. "
        "Only include fields the user actually stated or clearly implied — "
        "leave a field null/empty rather than guessing. Never invent "
        "coordinates; location_text is free text only (e.g. 'Fort, Mumbai'), "
        "never latitude/longitude.",
        "",
    ]
    for message in history:
        lines.append(f"{message.role}: {message.text}")
    lines.append(f"user: {user_message}")
    return "\n".join(lines)


def _traveler_context_to_args(context: TravelerContext) -> SearchExperiencesArgs:
    category_slug = next((slug for slug in context.category_slugs if slug in CATEGORY_SLUGS), None)
    return SearchExperiencesArgs(
        q=context.raw_query or None,
        category_slug=category_slug,
        limit=5,
    )


def _has_hard_constraints(context: TravelerContext) -> bool:
    """True when the extracted TravelerContext carries at least one hard
    feasibility constraint — the signal for routing this turn through
    DiscoveryPipelineService instead of the plain keyword search."""
    return any(
        (
            context.budget_min is not None,
            context.budget_max is not None,
            context.available_date is not None,
            context.available_start is not None,
            context.available_duration_minutes is not None,
            context.origin_lat is not None,
            context.max_distance_km is not None,
            context.max_travel_time_minutes is not None,
            bool(context.accessibility_requirements),
            bool(context.existing_commitments),
        )
    )


def _traveler_context_to_constraints(context: TravelerContext) -> TravelerConstraints:
    return TravelerConstraints(
        currency=context.currency or "INR",
        budget_min=context.budget_min,
        budget_max=context.budget_max,
        available_date=context.available_date,
        available_start=context.available_start,
        available_end=context.available_end,
        available_duration_minutes=context.available_duration_minutes,
        timezone=context.timezone,
        origin_lat=context.origin_lat,
        origin_lng=context.origin_lng,
        travel_mode=context.travel_mode,
        max_distance_km=context.max_distance_km,
        max_travel_time_minutes=context.max_travel_time_minutes,
        party_size=context.party_size,
        accessibility_requirements=context.accessibility_requirements,
        existing_commitments=context.existing_commitments,
    )


def _build_assistant_text(context: TravelerContext, result_count: int, total: int) -> str:
    if result_count == 0:
        return "I couldn't find experiences matching that yet — try adding a bit more detail."
    interests = ", ".join(context.interests[:3]) if context.interests else "your request"
    location = f" near {context.location_text}" if context.location_text else ""
    suffix = f" ({total} total, showing top {result_count})" if total > result_count else ""
    return f"Found {result_count} experiences matching {interests}{location}.{suffix}"


def _build_assistant_text_verified(
    context: TravelerContext, feasible_count: int, excluded_count: int
) -> str:
    if feasible_count == 0 and excluded_count == 0:
        return "I couldn't find experiences matching that yet — try adding a bit more detail."
    interests = ", ".join(context.interests[:3]) if context.interests else "your request"
    location = f" near {context.location_text}" if context.location_text else ""
    if feasible_count == 0:
        return (
            f"I found candidates matching {interests}{location}, but none satisfy all of your "
            f"constraints ({excluded_count} excluded) — try relaxing budget, time, or distance."
        )
    suffix = f" ({excluded_count} others didn't meet your constraints)" if excluded_count else ""
    return f"Found {feasible_count} verified-feasible experiences matching {interests}{location}.{suffix}"


async def create_conversation(session: AsyncSession, user_id: str, mode: str = "text") -> ConversationSession:
    conversation = ConversationSession(user_id=user_id, mode=mode)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def handle_text_turn(
    session: AsyncSession,
    ai: AIAdapter,
    settings: Settings,
    conversation: ConversationSession,
    user_message: str,
    embedding_adapter: EmbeddingAdapter | None = None,
    routing_adapter: RoutingAdapter | None = None,
) -> ConversationTurnResponse:
    history = await _recent_history(session, conversation.id, settings.conversation_history_window)

    user_row = ConversationMessage(session_id=conversation.id, role="user", text=user_message)
    session.add(user_row)

    prompt = _build_extraction_prompt(history, user_message)
    traveler_context = await ai.generate_text(prompt, response_schema=TravelerContext)

    if _has_hard_constraints(traveler_context) and embedding_adapter is not None and routing_adapter is not None:
        # Structured/templated response built from the verified pipeline —
        # never a free-form LLM feasibility verdict on the text path
        # either (docs/DECISIONS.md ADR-043).
        pipeline = DiscoveryPipelineService(session, settings, embedding_adapter, routing_adapter)
        category_slug = next((s for s in traveler_context.category_slugs if s in CATEGORY_SLUGS), None)
        pipeline_result = await pipeline.run(
            raw_query=traveler_context.raw_query,
            interests=traveler_context.interests or None,
            category_slug=category_slug,
            location_text=traveler_context.location_text,
            constraints=_traveler_context_to_constraints(traveler_context),
            travel_profile=settings.osrm_profile,
        )

        experience_repo = ExperienceRepository(session)
        summary_items = []
        for item in pipeline_result.items:
            experience = await experience_repo.get_by_id(item.experience_id)
            if experience is not None:
                summary_items.append(ExperienceSummary.model_validate(experience))

        tool_result = SearchExperiencesResult(
            items=summary_items, total=pipeline_result.candidate_count, truncated=False
        )
        assistant_text = _build_assistant_text_verified(
            traveler_context, pipeline_result.feasible_count, pipeline_result.excluded_count
        )
        tool_call_metadata = {
            "tool": "semantic_search_pipeline",
            "retrieval_mode": pipeline_result.retrieval_mode,
            "feasible_count": pipeline_result.feasible_count,
            "excluded_count": pipeline_result.excluded_count,
        }
    else:
        args = _traveler_context_to_args(traveler_context)
        tool_result = await execute_search_experiences(session, settings, args)
        assistant_text = _build_assistant_text(traveler_context, len(tool_result.items), tool_result.total)
        tool_call_metadata = {
            "tool": "search_experiences",
            "args": args.model_dump(exclude_none=True),
            "result_count": len(tool_result.items),
        }

    assistant_row = ConversationMessage(
        session_id=conversation.id,
        role="assistant",
        text=assistant_text,
        tool_call_metadata=tool_call_metadata,
    )
    session.add(assistant_row)

    conversation.latest_traveler_context = traveler_context.model_dump(mode="json")
    session.add(conversation)

    await session.commit()
    await session.refresh(assistant_row)

    return ConversationTurnResponse(
        message_id=assistant_row.id,
        assistant_text=assistant_text,
        traveler_context=traveler_context,
        tool_results=tool_result,
    )


__all__ = ["create_conversation", "handle_text_turn"]
