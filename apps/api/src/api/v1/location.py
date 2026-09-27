"""Location endpoints — geocoding, routing, nearby OSM POIs.

Every external call goes through the adapters in src/adapters/ — no
route handler here ever calls httpx directly (docs/DECISIONS.md ADR-022).
Search/reverse are only ever invoked by an explicit user action from the
frontend; there is deliberately no autocomplete route.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.adapters.errors import AdapterNoResultError, AdapterRateLimitedError, AdapterUnavailableError
from src.adapters.geocoding import GeocodingAdapter
from src.adapters.poi import POI_CATEGORY_TAGS, POIAdapter
from src.adapters.routing import OSRMRoutingAdapter, RoutingAdapter
from src.core.config import Settings, get_settings
from src.core.errors import ApiError
from src.core.geo import validate_coordinates
from src.core.location import get_geocoding_adapter, get_poi_adapter, get_routing_adapter
from src.schemas.location import (
    LocationSearchResponse,
    LocationSearchResponseItem,
    NearbyPOIResponse,
    NearbyPOIResponseItem,
    RouteRequest,
    RouteResponse,
    TravelTimeMatrixEntry,
    TravelTimeMatrixRequest,
    TravelTimeMatrixResponse,
)

router = APIRouter(prefix="/location", tags=["location"])


def _translate_adapter_error(exc: Exception) -> ApiError:
    if isinstance(exc, AdapterRateLimitedError):
        return ApiError("The location service is temporarily rate-limited. Please try again shortly.", 503)
    if isinstance(exc, AdapterNoResultError):
        return ApiError("No result found.", 404)
    if isinstance(exc, AdapterUnavailableError):
        return ApiError("The location service is temporarily unavailable.", 503)
    if isinstance(exc, ValueError):
        return ApiError(str(exc), 422)
    return ApiError("Unexpected location service error.", 503)


@router.get("/search", response_model=LocationSearchResponse)
async def search_location(
    q: Annotated[str, Query(min_length=2, max_length=200)],
    geocoding: Annotated[GeocodingAdapter, Depends(get_geocoding_adapter)],
) -> LocationSearchResponse:
    try:
        results = await geocoding.search(q, limit=5)
    except Exception as exc:  # noqa: BLE001 — normalized below
        raise _translate_adapter_error(exc) from exc

    return LocationSearchResponse(
        items=[
            LocationSearchResponseItem(
                display_name=r.display_name, lat=r.lat, lng=r.lng, city=r.city,
                locality=r.locality, state=r.state, country=r.country, source=r.source,
            )
            for r in results
        ]
    )


@router.get("/reverse", response_model=LocationSearchResponse)
async def reverse_geocode(
    geocoding: Annotated[GeocodingAdapter, Depends(get_geocoding_adapter)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
) -> LocationSearchResponse:
    try:
        result = await geocoding.reverse(lat, lng)
    except Exception as exc:  # noqa: BLE001
        raise _translate_adapter_error(exc) from exc

    if result is None:
        return LocationSearchResponse(items=[])
    return LocationSearchResponse(
        items=[
            LocationSearchResponseItem(
                display_name=result.display_name, lat=result.lat, lng=result.lng, city=result.city,
                locality=result.locality, state=result.state, country=result.country, source=result.source,
            )
        ]
    )


@router.get("/nearby-pois", response_model=NearbyPOIResponse)
async def nearby_pois(
    poi: Annotated[POIAdapter, Depends(get_poi_adapter)],
    settings: Annotated[Settings, Depends(get_settings)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[int, Query(ge=50, le=2000)] = 500,
    categories: Annotated[str, Query(description="Comma-separated category allowlist")] = "restaurant,cafe",
) -> NearbyPOIResponse:
    validate_coordinates(lat, lng)
    if radius_m > settings.overpass_max_radius_m:
        raise ApiError(f"radius_m may not exceed {settings.overpass_max_radius_m}", 422)

    category_list = [c.strip() for c in categories.split(",") if c.strip()]
    unknown = set(category_list) - set(POI_CATEGORY_TAGS)
    if unknown:
        raise ApiError(f"Unknown POI categories: {sorted(unknown)}", 422)

    try:
        results = await poi.search_nearby(lat, lng, radius_m, category_list)
    except Exception as exc:  # noqa: BLE001
        raise _translate_adapter_error(exc) from exc

    return NearbyPOIResponse(
        items=[
            NearbyPOIResponseItem(
                osm_type=r.osm_type, osm_id=r.osm_id, name=r.name, category=r.category,
                lat=r.lat, lng=r.lng, tags=r.tags, distance_km=r.distance_km,
            )
            for r in results
        ],
        categories_available=sorted(POI_CATEGORY_TAGS),
    )


@router.post("/route", response_model=RouteResponse)
async def get_route(
    payload: RouteRequest,
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
) -> RouteResponse:
    try:
        result = await routing.get_route(
            (payload.origin.lat, payload.origin.lng),
            (payload.destination.lat, payload.destination.lng),
            profile=payload.profile,
            include_geometry=payload.include_geometry,
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate_adapter_error(exc) from exc

    return RouteResponse(
        distance_km=result.distance_km,
        duration_minutes=result.duration_minutes,
        geometry=result.geometry,
        source=result.source,  # type: ignore[arg-type]
    )


@router.post("/travel-time-matrix", response_model=TravelTimeMatrixResponse)
async def travel_time_matrix(
    payload: TravelTimeMatrixRequest,
    routing: Annotated[RoutingAdapter, Depends(get_routing_adapter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TravelTimeMatrixResponse:
    if len(payload.destinations) > settings.osrm_max_matrix_destinations:
        raise ApiError(
            f"Cannot request more than {settings.osrm_max_matrix_destinations} destinations at once", 422
        )

    try:
        entries = await routing.get_travel_time_matrix(
            (payload.origin.lat, payload.origin.lng),
            [(d.id, d.lat, d.lng) for d in payload.destinations],
            profile=payload.profile,
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate_adapter_error(exc) from exc

    source = "osrm" if isinstance(routing, OSRMRoutingAdapter) else "haversine_estimate"
    return TravelTimeMatrixResponse(
        source=source,  # type: ignore[arg-type]
        profile=payload.profile,
        destinations=[
            TravelTimeMatrixEntry(id=e.id, distance_km=e.distance_km, duration_minutes=e.duration_minutes)
            for e in entries
        ],
    )
