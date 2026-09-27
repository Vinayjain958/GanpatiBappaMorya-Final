"""Explicit traveler-triggered what-if preview and apply endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.embedding import EmbeddingAdapter
from src.adapters.errors import AdapterError
from src.adapters.routing import RoutingAdapter
from src.adapters.weather import WeatherAdapter
from src.core.ai import get_ai_adapter
from src.core.config import Settings, get_settings
from src.core.context import get_weather_adapter
from src.core.db import get_session
from src.core.deps import require_traveler
from src.core.digital_twin import get_domain_intelligence_provider, simulation_session_store
from src.core.embedding import get_embedding_adapter
from src.core.errors import ApiError
from src.core.location import get_routing_adapter
from src.core.social_signals import get_social_signal_service
from src.models.user import User
from src.schemas.digital_twin import SimulationResult, WhatIfScenario
from src.schemas.replanning import ReplanChangeSetResponse, ReplanResponse
from src.services.digital_twin import DigitalTwinService
from src.services.replanning import ReplanningService
from src.services.social_signals import SocialSignalService

router = APIRouter(prefix="/digital-twin", tags=["digital-twin-simulation"])


def _service(
    *,
    session: AsyncSession,
    settings: Settings,
    weather: WeatherAdapter,
    routing: RoutingAdapter,
    social: SocialSignalService,
    embedding: EmbeddingAdapter | None = None,
) -> DigitalTwinService:
    return DigitalTwinService(
        session=session,
        settings=settings,
        weather=weather,
        routing=routing,
        embedding=embedding,
        social=social,
        intelligence=get_domain_intelligence_provider(settings),
    )


@router.post("/itineraries/{itinerary_id}/simulate", response_model=SimulationResult)
async def simulate_itinerary(
    itinerary_id: str,
    payload: WhatIfScenario,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    weather: Annotated[WeatherAdapter, Depends(get_weather_adapter)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    embedding: Annotated[EmbeddingAdapter, Depends(get_embedding_adapter)],
    social: Annotated[SocialSignalService, Depends(get_social_signal_service)],
) -> SimulationResult:
    """Return an ephemeral preview. This endpoint never writes itinerary state."""
    if user.traveler is None:
        raise ApiError("Traveler profile not found", status_code=404)
    try:
        return await _service(
            session=session,
            settings=settings,
            weather=weather,
            routing=routing,
            social=social,
            embedding=embedding,
        ).simulate(itinerary_id=itinerary_id, traveler_id=user.traveler.id, scenario=payload)
    except LookupError as exc:
        raise ApiError("Itinerary not found", status_code=404) from exc
    except ValueError as exc:
        raise ApiError(str(exc), status_code=422) from exc
    except AdapterError as exc:
        raise ApiError(
            "Domain intelligence is temporarily unavailable. Retry the preview later.", status_code=503
        ) from exc


@router.post("/simulations/{simulation_id}/apply", response_model=ReplanResponse)
async def apply_simulation(
    simulation_id: str,
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    embedding: Annotated[EmbeddingAdapter, Depends(get_embedding_adapter)],
    ai: Annotated[AIAdapter, Depends(get_ai_adapter)],
) -> ReplanResponse:
    """Explicitly apply a still-current preview through ReplanningService."""
    if user.traveler is None:
        raise ApiError("Traveler profile not found", status_code=404)
    stored = simulation_session_store.get(simulation_id)
    if stored is None:
        raise ApiError("Simulation preview expired or was not found. Run it again.", status_code=410)
    if stored.owner_id != user.traveler.id:
        raise ApiError("Simulation preview not found", status_code=404)
    service = _service(
        session=session,
        settings=settings,
        weather=get_weather_adapter(),
        routing=routing,
        social=get_social_signal_service(),
    )
    current = await service.get_owned_simulation(simulation_id=simulation_id, traveler_id=user.traveler.id)
    if current is None:
        simulation_session_store.remove(simulation_id)
        raise ApiError("The itinerary changed after this preview. Run the simulation again.", status_code=409)
    outcome = await ReplanningService(
        session=session,
        settings=settings,
        routing_adapter=routing,
        embedding_adapter=embedding,
        ai_adapter=ai,
    ).replan_itinerary(
        itinerary_id=stored.itinerary_id,
        traveler_id=user.traveler.id,
        trigger="USER_REQUESTED",
        impact=stored.impact,
        expected_version=stored.itinerary_version,
        idempotency_key=f"what-if:{simulation_id}",
        reason=f"Apply what-if scenario: {stored.scenario.name}",
    )
    if outcome.reason_code == "ITINERARY_VERSION_CONFLICT":
        simulation_session_store.remove(simulation_id)
        raise ApiError("The itinerary changed after this preview. Run the simulation again.", status_code=409)
    return ReplanResponse(
        status=outcome.status,
        itinerary_id=stored.itinerary_id,
        previous_version=outcome.previous_version,
        new_version=outcome.new_version,
        trigger=outcome.trigger,
        changes=ReplanChangeSetResponse(
            added_items=outcome.changes.added_items,
            removed_items=outcome.changes.removed_items,
            moved_items=outcome.changes.moved_items,
            unchanged_items=outcome.changes.unchanged_items,
            affected_items=outcome.changes.affected_items,
        ),
        context_summary=outcome.context_summary,
        validation_issues=outcome.validation_issues,
        reason_code=outcome.reason_code,
        message=outcome.message,
        generated_at=outcome.generated_at,
    )


__all__ = ["router"]
