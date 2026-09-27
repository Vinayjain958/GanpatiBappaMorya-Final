"""POIAdapter interface — Overpass API.

Overpass has no hard published rate limit but a documented fair-use
ceiling (~10k req/day, ~1GB/day per the OSMF ops wiki) and actively
load-sheds (HTTP 429/504) under contention — this adapter self-throttles
conservatively and never accepts arbitrary Overpass QL from the client
(docs/DECISIONS.md ADR-022/ADR-024): only a small server-side category
allowlist maps to OSM tags, and the query is always built server-side
from validated lat/lng/radius/categories.

Overpass results are contextual OSM points of interest — they are never
automatically turned into LocaLens `Experience` catalog rows (see
docs/AI_CONTEXT.md INV-9/INV-14 and ADR-024).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from src.adapters.errors import AdapterRateLimitedError, AdapterUnavailableError
from src.core.cache import TTLCache
from src.core.config import Settings
from src.core.geo import haversine_km
from src.core.http_client import get_http_client
from src.core.rate_limit import IntervalRateLimiter

# category -> one or more OSM "key=value" tag filters (OR'd together).
POI_CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "museum": [("tourism", "museum")],
    "gallery": [("tourism", "gallery"), ("shop", "art")],
    "attraction": [("tourism", "attraction")],
    "market": [("shop", "marketplace"), ("amenity", "marketplace")],
    "park": [("leisure", "park")],
    "theatre": [("amenity", "theatre")],
    "library": [("amenity", "library")],
    "viewpoint": [("tourism", "viewpoint")],
    "arts_center": [("amenity", "arts_centre")],
}


@dataclass(frozen=True)
class POIResult:
    osm_type: str
    osm_id: int
    name: str
    category: str
    lat: float
    lng: float
    tags: dict[str, str]
    distance_km: float


class POIAdapter(Protocol):
    async def search_nearby(
        self, lat: float, lng: float, radius_m: int, categories: list[str]
    ) -> list[POIResult]: ...


class MockPOIAdapter:
    async def search_nearby(
        self, lat: float, lng: float, radius_m: int, categories: list[str]
    ) -> list[POIResult]:
        return []


def _build_overpass_query(lat: float, lng: float, radius_m: int, categories: list[str]) -> str:
    tag_filters: list[tuple[str, str]] = []
    for category in categories:
        tag_filters.extend(POI_CATEGORY_TAGS[category])

    clauses = "\n".join(
        f'  node(around:{radius_m},{lat},{lng})["{key}"="{value}"];' for key, value in tag_filters
    )
    return f"[out:json][timeout:15];\n(\n{clauses}\n);\nout body;"


class OverpassPOIAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._limiter = IntervalRateLimiter(settings.overpass_min_interval_seconds)
        self._cache: TTLCache[list[POIResult]] = TTLCache(settings.overpass_cache_ttl_seconds)

    async def search_nearby(
        self, lat: float, lng: float, radius_m: int, categories: list[str]
    ) -> list[POIResult]:
        if radius_m > self._settings.overpass_max_radius_m:
            raise ValueError(
                f"radius_m {radius_m} exceeds the configured maximum "
                f"{self._settings.overpass_max_radius_m}"
            )
        unknown = set(categories) - set(POI_CATEGORY_TAGS)
        if unknown:
            raise ValueError(f"Unknown POI categories: {sorted(unknown)}")
        if not categories:
            return []

        # Round the origin for cache-key stability across near-identical requests.
        cache_key = f"{round(lat, 3)}:{round(lng, 3)}:{radius_m}:{sorted(categories)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        query = _build_overpass_query(lat, lng, radius_m, categories)

        await self._limiter.wait()
        client = get_http_client()
        try:
            response = await client.post(self._settings.overpass_base_url, data={"data": query})
        except httpx.TimeoutException as exc:
            raise AdapterUnavailableError("Overpass request timed out") from exc
        except httpx.HTTPError as exc:
            raise AdapterUnavailableError(f"Overpass request failed: {exc}") from exc

        if response.status_code == 429 or response.status_code == 504:
            retry_after = response.headers.get("Retry-After")
            raise AdapterRateLimitedError(
                "Overpass is rate-limiting/load-shedding this client",
                retry_after_seconds=float(retry_after) if retry_after else None,
            )
        if response.status_code >= 400:
            raise AdapterUnavailableError(f"Overpass returned HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterUnavailableError("Overpass returned malformed JSON") from exc

        category_by_tags = {tag: cat for cat, tags in POI_CATEGORY_TAGS.items() for tag in tags}
        results: list[POIResult] = []
        for element in body.get("elements", []):
            if element.get("type") != "node" or "lat" not in element or "lon" not in element:
                continue
            tags = element.get("tags") or {}
            matched_category = next(
                (
                    category_by_tags[(k, v)]
                    for k, v in tags.items()
                    if (k, v) in category_by_tags
                ),
                categories[0],
            )
            results.append(
                POIResult(
                    osm_type=element["type"],
                    osm_id=element["id"],
                    name=tags.get("name", "Unnamed location"),
                    category=matched_category,
                    lat=element["lat"],
                    lng=element["lon"],
                    tags=tags,
                    distance_km=round(haversine_km(lat, lng, element["lat"], element["lon"]), 3),
                )
            )

        results.sort(key=lambda r: r.distance_km)
        self._cache.set(cache_key, results)
        return results


__all__ = [
    "MockPOIAdapter",
    "OverpassPOIAdapter",
    "POIAdapter",
    "POIResult",
    "POI_CATEGORY_TAGS",
]
