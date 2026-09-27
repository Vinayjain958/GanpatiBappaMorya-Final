"""Nearby safety-resource lookup — hospitals, police, consulates/embassies.

SAFETY_RESOURCES_MODE:
  auto (default): try the live OSM/Overpass adapter first; if that
    genuinely fails, try the Mapbox adapter (when MAPBOX_API_KEY is
    configured); fall back to the deterministic seed adapter only after
    both live providers fail — never merely because a live query
    returned zero results.
  live: never falls back to seed; still tries Overpass then Mapbox, but
    a failure of both surfaces as an explicit service error.
  fallback: always uses the seed adapter (explicit test/demo mode).
"""

from __future__ import annotations

import logging

from src.core.config import Settings, get_settings
from src.schemas.safety import SafetyResource
from src.services.safety.resource_adapters import (
    MapboxSafetyResourceAdapter,
    OSMSafetyResourceAdapter,
    SafetyAdapterError,
    SeedSafetyResourceAdapter,
)

logger = logging.getLogger(__name__)


class SafetyResourceServiceError(Exception):
    """Raised in `live` mode when the live provider fails — the caller
    must surface this as an honest error, never silently substitute
    fabricated data."""


class InvalidRadiusError(ValueError):
    pass


def _validate_radius(radius_km: float, settings: Settings) -> None:
    if radius_km < settings.safety_resources_min_radius_km or radius_km > settings.safety_resources_max_radius_km:
        raise InvalidRadiusError(
            f"radius_km must be between {settings.safety_resources_min_radius_km} and "
            f"{settings.safety_resources_max_radius_km}, got {radius_km}"
        )


async def get_nearby_safety_resources(
    lat: float,
    lng: float,
    radius_km: float,
    category: str | None,
    settings: Settings | None = None,
) -> list[SafetyResource]:
    settings = settings or get_settings()
    _validate_radius(radius_km, settings)

    mode = settings.safety_resources_mode

    if mode == "fallback":
        adapter = SeedSafetyResourceAdapter()
        return await adapter.get_nearby_resources(lat, lng, radius_km, category)

    osm_adapter = OSMSafetyResourceAdapter(settings)
    try:
        return await osm_adapter.get_nearby_resources(lat, lng, radius_km, category)
    except SafetyAdapterError as osm_exc:
        logger.warning("Overpass safety resource adapter failed: %s", osm_exc)

        mapbox_adapter = MapboxSafetyResourceAdapter(settings)
        try:
            return await mapbox_adapter.get_nearby_resources(lat, lng, radius_km, category)
        except SafetyAdapterError as mapbox_exc:
            logger.warning("Mapbox safety resource adapter failed: %s", mapbox_exc)

            if mode == "live":
                raise SafetyResourceServiceError(
                    f"Live safety resource lookup failed (Overpass: {osm_exc}; Mapbox: {mapbox_exc})"
                ) from mapbox_exc

            # auto — both live providers failed, fall back to seed data.
            fallback = SeedSafetyResourceAdapter()
            return await fallback.get_nearby_resources(lat, lng, radius_km, category)


__all__ = ["get_nearby_safety_resources", "SafetyResourceServiceError", "InvalidRadiusError"]
