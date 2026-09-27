"""FastAPI dependency providers for the Phase 9 real-time context adapters.

Selects the real OpenWeatherAdapter/TicketmasterEventAdapter unless
`CONTEXT_SERVICES_ENABLED=false` or the relevant API key is absent, in
which case the Mock/Seed adapter is used — mirrors src/core/location.py's
and src/core/ai.py's fallback pattern exactly. Per-process singletons so
each adapter's cache/rate-limiter state persists across requests.
"""

from __future__ import annotations

from functools import lru_cache

from src.adapters.events import EventAdapter, SeedEventAdapter, TicketmasterEventAdapter
from src.adapters.weather import MockWeatherAdapter, OpenWeatherAdapter, WeatherAdapter
from src.core.config import get_settings


@lru_cache
def get_weather_adapter() -> WeatherAdapter:
    settings = get_settings()
    if not (settings.context_services_enabled and settings.openweather_api_key):
        return MockWeatherAdapter()
    return OpenWeatherAdapter(settings)


@lru_cache
def get_event_adapter() -> EventAdapter:
    settings = get_settings()
    if not (settings.context_services_enabled and settings.ticketmaster_api_key):
        return SeedEventAdapter()
    return TicketmasterEventAdapter(settings)


__all__ = ["get_event_adapter", "get_weather_adapter"]
