"""Application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_v1_router
from src.core.ai import get_ai_adapter
from src.core.config import get_settings
from src.core.context import get_event_adapter, get_weather_adapter
from src.core.db import async_session_factory
from src.core.embedding import get_embedding_adapter
from src.core.errors import register_error_handlers
from src.core.location import get_routing_adapter
from src.core.logging import configure_logging
from src.core.startup import validate_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    validate_startup(settings)
    monitor = None

    # Only live weather may drive the background impact/replan flow. The
    # mock adapter remains available to the UI as MOCK, but mock conditions
    # must never be mistaken for real conditions by automatic replanning.
    if settings.context_services_enabled and settings.openweather_api_key:
        from src.models.itinerary import Itinerary
        from src.services.context_impact import ContextImpactResult
        from src.services.context_monitor import get_context_monitor
        from src.services.replanning import ReplanningService

        async def replan_after_weather_change(
            itinerary_id: str, trigger: str, impact: object
        ) -> None:
            if not settings.replanning_enabled or not isinstance(impact, ContextImpactResult):
                return
            async with async_session_factory() as session:
                itinerary = await session.get(Itinerary, itinerary_id)
                if itinerary is None:
                    return
                outcome = await ReplanningService(
                    session=session,
                    settings=settings,
                    routing_adapter=get_routing_adapter(),
                    embedding_adapter=get_embedding_adapter(),
                    ai_adapter=get_ai_adapter(),
                ).replan_itinerary(
                    itinerary_id=itinerary_id,
                    traveler_id=itinerary.traveler_id,
                    trigger=trigger,
                    impact=impact,
                )
                logger.info(
                    "Context monitor replan finished",
                    extra={"itinerary_id": itinerary_id, "status": outcome.status},
                )

        monitor = get_context_monitor(
            settings=settings,
            session_factory=async_session_factory,
            weather_adapter=get_weather_adapter(),
            event_adapter=get_event_adapter(),
            replan_callback=replan_after_weather_change,
        )
        monitor.start()
        app.state.context_monitor = monitor

    try:
        yield
    finally:
        if monitor is not None:
            await monitor.stop()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="LocaLens API",
        version="0.3.0",
        description=(
            "LocaLens backend. Authenticated endpoints use a short-lived "
            "Bearer access token (Authorization: Bearer <token>); the "
            "refresh token travels only as an HttpOnly cookie and is "
            "never part of the JSON API surface."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_v1_router)

    return app
