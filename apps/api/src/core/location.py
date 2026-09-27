"""FastAPI dependency providers for the location adapters.

Selects the real Nominatim/OSRM/Overpass adapter unless
`LOCATION_SERVICES_ENABLED=false`, in which case the Mock*Adapter is used
instead — this keeps the app fully runnable offline (docs/AI_CONTEXT.md
adapter fallback contract), e.g. in CI or a network-restricted demo room.
Each adapter is a per-process singleton so its cache/rate-limiter state
persists across requests.
"""

from __future__ import annotations

from functools import lru_cache

from src.adapters.geocoding import GeocodingAdapter, MockGeocodingAdapter, NominatimGeocodingAdapter
from src.adapters.poi import MockPOIAdapter, OverpassPOIAdapter, POIAdapter
from src.adapters.routing import MockRoutingAdapter, OSRMRoutingAdapter, RoutingAdapter
from src.core.config import get_settings


@lru_cache
def get_geocoding_adapter() -> GeocodingAdapter:
    settings = get_settings()
    if not settings.location_services_enabled:
        return MockGeocodingAdapter()
    return NominatimGeocodingAdapter(settings)


@lru_cache
def get_routing_adapter() -> RoutingAdapter:
    settings = get_settings()
    if not settings.location_services_enabled:
        return MockRoutingAdapter()
    return OSRMRoutingAdapter(settings)


@lru_cache
def get_poi_adapter() -> POIAdapter:
    settings = get_settings()
    if not settings.location_services_enabled:
        return MockPOIAdapter()
    return OverpassPOIAdapter(settings)
