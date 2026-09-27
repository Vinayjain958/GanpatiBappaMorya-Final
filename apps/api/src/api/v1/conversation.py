"""Conversational discovery endpoints (Phase 5).

Text turns go through handle_text_turn (understand -> retrieve, one
Gemini call per turn). The tool-calls route is the voice-path bridge:
Gemini Live runs entirely browser<->Google, and the browser forwards each
tool_call here for real, backend-owned execution — the browser itself
never implements search_experiences (docs/AI_CONTEXT.md INV-3,
docs/DECISIONS.md ADR-034).

Ownership: every route requires CurrentUser and 404s (never discloses
existence via 403) for another user's conversation, matching the
non-disclosure pattern already used for provider-owned experiences.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.embedding import EmbeddingAdapter
from src.adapters.errors import AdapterError, AdapterNoResultError, AdapterRateLimitedError, AdapterUnavailableError
from src.adapters.routing import RoutingAdapter
from src.adapters.weather import WeatherAdapter
from src.core.ai import get_ai_adapter
from src.core.config import Settings, get_settings
from src.core.context import get_weather_adapter
from src.core.db import get_session
from src.core.deps import CurrentUser
from src.core.embedding import get_embedding_adapter
from src.core.errors import ApiError
from src.core.location import get_routing_adapter
from src.core.social_signals import get_social_signal_service
from src.models.conversation_message import ConversationMessage
from src.models.conversation_session import ConversationSession
from src.models.traveler import Traveler
from src.repositories.conversation_repository import ConversationRepository
from src.schemas.conversation import (
    CheckFeasibilityArgs,
    ComposeExperienceArgs,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationMessagePublic,
    ConversationTurnRequest,
    ConversationTurnResponse,
    ReplanExperienceArgs,
    SearchExperiencesArgs,
    SearchExperiencesResult,
    SimulateWhatIfArgs,
    ToolCallRequest,
    TravelerContext,
)
from src.schemas.feasibility import FeasibilityVerdict
from src.schemas.itinerary import ItineraryResponse
from src.services import ai_tools
from src.services.conversation import create_conversation, handle_text_turn
from src.services.social_signals import SocialSignalService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _translate_ai_error(exc: Exception) -> ApiError:
    if isinstance(exc, AdapterRateLimitedError):
        return ApiError("The AI service is temporarily rate-limited. Please try again shortly.", 503)
    if isinstance(exc, AdapterNoResultError):
        return ApiError("The AI service returned no usable result.", 503)
    if isinstance(exc, AdapterUnavailableError):
        return ApiError("The AI service is temporarily unavailable.", 503)
    if isinstance(exc, ValueError):
        return ApiError(str(exc), 422)
    return ApiError("Unexpected AI service error.", 503)


async def _get_owned_or_404(session: AsyncSession, conversation_id: str, user_id: str) -> ConversationSession:
    conversation = await ConversationRepository(session).get_owned_by_id(conversation_id, user_id)
    if conversation is None:
        # Deliberately identical to "does not exist" — never disclose that
        # a conversation exists but belongs to another user.
        raise ApiError("Conversation not found", status_code=404)
    return conversation


@router.post("", response_model=ConversationCreateResponse, status_code=201)
async def create_conversation_session(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationCreateResponse:
    conversation = await create_conversation(session, user.id, mode="text")
    return ConversationCreateResponse(id=conversation.id, created_at=conversation.created_at)


@router.post("/{conversation_id}/messages", response_model=ConversationTurnResponse)
async def send_message(
    conversation_id: str,
    payload: ConversationTurnRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    ai: Annotated[AIAdapter, Depends(get_ai_adapter)],
    embedding_adapter: Annotated[EmbeddingAdapter, Depends(get_embedding_adapter)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
) -> ConversationTurnResponse:
    conversation = await _get_owned_or_404(session, conversation_id, user.id)
    try:
        return await handle_text_turn(
            session, ai, settings, conversation, payload.message, embedding_adapter, routing
        )
    except AdapterError as exc:
        raise _translate_ai_error(exc) from exc
    except ValueError as exc:
        raise _translate_ai_error(exc) from exc


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationDetailResponse:
    conversation = await _get_owned_or_404(session, conversation_id, user.id)
    messages = [ConversationMessagePublic.model_validate(m) for m in conversation.messages]
    latest_context = (
        TravelerContext.model_validate(conversation.latest_traveler_context)
        if conversation.latest_traveler_context is not None
        else None
    )
    return ConversationDetailResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        messages=messages,
        latest_traveler_context=latest_context,
    )


_KNOWN_TOOLS = {
    "search_experiences",
    "check_feasibility",
    "compose_experience",
    "replan_experience",
    "simulate_what_if",
}


@router.post(
    "/{conversation_id}/tool-calls",
    response_model=SearchExperiencesResult | FeasibilityVerdict | ItineraryResponse | dict[str, object],
)
async def execute_tool_call(
    conversation_id: str,
    payload: ToolCallRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    embedding_adapter: Annotated[EmbeddingAdapter, Depends(get_embedding_adapter)],
    weather_adapter: Annotated[WeatherAdapter, Depends(get_weather_adapter)],
    social_service: Annotated[SocialSignalService, Depends(get_social_signal_service)],
    ai: Annotated[AIAdapter, Depends(get_ai_adapter)],
) -> SearchExperiencesResult | FeasibilityVerdict | ItineraryResponse | dict[str, object]:
    """Voice-path bridge: the browser forwards Gemini Live's tool_call
    here verbatim and forwards this response back to Gemini via
    session.send_tool_response(...). This endpoint — not the browser —
    is the only place search_experiences/check_feasibility/
    compose_experience/replan_experience actually execute; all four
    tools are backend-owned per the allowlist above. Unknown tool names
    fail safely with a 422 below rather than being silently dispatched."""
    conversation = await _get_owned_or_404(session, conversation_id, user.id)

    if payload.name not in _KNOWN_TOOLS:
        raise ApiError(f"Unknown tool: {payload.name}", status_code=422)

    # traveler_id is server-derived: a `traveler`-role user has exactly
    # one Traveler row (see registration); a `provider`-role user has
    # none, so traveler_id is None and the anonymous (unranked) path is
    # used where applicable — never trust a client-supplied traveler id.
    from sqlalchemy import select

    traveler_id = await session.scalar(select(Traveler.id).where(Traveler.user_id == user.id))

    if payload.name == "simulate_what_if":
        if traveler_id is None:
            raise ApiError("Not authenticated", status_code=401)
        try:
            simulation_args = SimulateWhatIfArgs.model_validate(payload.args)
        except Exception as exc:  # noqa: BLE001 — model tool arguments are untrusted
            raise ApiError(f"Invalid tool arguments: {exc}", status_code=422) from exc
        simulation_result = await ai_tools.execute_simulate_what_if(
            session=session,
            settings=settings,
            routing_adapter=routing,
            embedding_adapter=embedding_adapter,
            weather_adapter=weather_adapter,
            social_service=social_service,
            args=simulation_args,
            traveler_id=traveler_id,
        )
        session.add(
            ConversationMessage(
                session_id=conversation.id,
                role="assistant",
                text="[voice tool call] simulate_what_if -> preview generated",
                tool_call_metadata={
                    "tool": "simulate_what_if",
                    "itinerary_id": simulation_args.itinerary_id,
                    "simulation_id": simulation_result["simulation_id"],
                    "status": simulation_result["status"],
                },
            )
        )
        await session.commit()
        return simulation_result

    if payload.name == "search_experiences":
        try:
            args = SearchExperiencesArgs.model_validate(payload.args)
        except Exception as exc:  # noqa: BLE001 — never trust raw model tool arguments
            raise ApiError(f"Invalid tool arguments: {exc}", status_code=422) from exc

        # latest_traveler_context is stored as a raw JSON dict (see
        # models/conversation_session.py) — must be validated into a real
        # TravelerContext before use. Passing the raw dict through
        # unvalidated previously worked only because nothing downstream
        # happened to attribute-access it in the paths existing tests
        # covered; WeightedPersonalizedRanker.rank() does read
        # context.budget_max, which would raise AttributeError on a plain
        # dict the moment this conversation's context carried a budget.
        traveler_context = (
            TravelerContext.model_validate(conversation.latest_traveler_context)
            if conversation.latest_traveler_context is not None
            else None
        )

        result, ranked_items = await ai_tools.execute_search_experiences_with_candidates(
            session=session,
            settings=settings,
            args=args,
            traveler_id=traveler_id,
            context=traveler_context,
            routing_adapter=routing,
            embedding_adapter=embedding_adapter,
        )

        # Cache the authorized candidate context for a subsequent
        # compose_experience call in THIS conversation — overwritten by
        # every new search, never trusted blindly by compose_experience.
        if ranked_items is not None:
            conversation.last_search_candidates = [item.model_dump(mode="json") for item in ranked_items]

        session.add(
            ConversationMessage(
                session_id=conversation.id,
                role="assistant",
                text=f"[voice tool call] search_experiences -> {len(result.items)} result(s)",
                tool_call_metadata={
                    "tool": "search_experiences",
                    "args": args.model_dump(exclude_none=True),
                    "result_count": len(result.items),
                },
            )
        )
        await session.commit()
        return result

    if payload.name == "compose_experience":
        try:
            compose_args = ComposeExperienceArgs.model_validate(payload.args)
        except Exception as exc:  # noqa: BLE001 — never trust raw model tool arguments
            raise ApiError(f"Invalid tool arguments: {exc}", status_code=422) from exc

        if traveler_id is None:
            raise ApiError("Not authenticated", status_code=401)

        outcome = await ai_tools.execute_compose_experience(
            session=session,
            settings=settings,
            routing_adapter=routing,
            embedding_adapter=embedding_adapter,
            ai_adapter=ai,
            args=compose_args,
            traveler_id=traveler_id,
            candidate_context=conversation.last_search_candidates,
        )

        session.add(
            ConversationMessage(
                session_id=conversation.id,
                role="assistant",
                text="[voice tool call] compose_experience",
                tool_call_metadata={
                    "tool": "compose_experience",
                    "args": compose_args.model_dump(mode="json", exclude_none=True),
                },
            )
        )
        await session.commit()
        return outcome

    if payload.name == "replan_experience":
        try:
            replan_args = ReplanExperienceArgs.model_validate(payload.args)
        except Exception as exc:  # noqa: BLE001 — never trust raw model tool arguments
            raise ApiError(f"Invalid tool arguments: {exc}", status_code=422) from exc

        if traveler_id is None:
            raise ApiError("Not authenticated", status_code=401)

        replan_result = await ai_tools.execute_replan_experience(
            session=session,
            settings=settings,
            routing_adapter=routing,
            embedding_adapter=embedding_adapter,
            ai_adapter=ai,
            args=replan_args,
            traveler_id=traveler_id,
        )

        session.add(
            ConversationMessage(
                session_id=conversation.id,
                role="assistant",
                text=f"[voice tool call] replan_experience -> {replan_result.get('status')}",
                tool_call_metadata={
                    "tool": "replan_experience",
                    "args": replan_args.model_dump(mode="json", exclude_none=True),
                    "status": replan_result.get("status"),
                },
            )
        )
        await session.commit()
        return replan_result

    # check_feasibility
    try:
        feasibility_args = CheckFeasibilityArgs.model_validate(payload.args)
    except Exception as exc:  # noqa: BLE001 — never trust raw model tool arguments
        raise ApiError(f"Invalid tool arguments: {exc}", status_code=422) from exc

    verdict = await ai_tools.execute_check_feasibility(session, routing, settings, feasibility_args)

    session.add(
        ConversationMessage(
            session_id=conversation.id,
            role="assistant",
            text=f"[voice tool call] check_feasibility -> {verdict.status}",
            tool_call_metadata={
                "tool": "check_feasibility",
                "args": feasibility_args.model_dump(exclude_none=True),
                "status": verdict.status,
            },
        )
    )
    await session.commit()
    return verdict
