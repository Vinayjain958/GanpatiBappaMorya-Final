"""Safety resource adapters — hospitals, police stations, and
consulates/embassies near a traveler's real coordinates.

OSMSafetyResourceAdapter queries the Overpass API directly (no PostGIS,
no dependency on the recommendation/discovery domain — see
tests/test_safety_isolation.py). SeedSafetyResourceAdapter is a
deterministic, clearly-labelled (`is_synthetic=True`) fallback used only
when the live provider genuinely fails (network error, timeout,
malformed response) or when SAFETY_RESOURCES_MODE forces it — never
merely because a live query returned zero results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import httpx

from src.core.cache import TTLCache
from src.core.config import Settings
from src.core.geo import haversine_km, validate_coordinates
from src.core.http_client import get_http_client
from src.core.rate_limit import IntervalRateLimiter
from src.schemas.safety import SafetyResource

# category -> OSM "key=value" tag filters (OR'd together). Legacy
# amenity=embassy/consulate tags are included for coverage alongside the
# current office=diplomatic + diplomatic=* convention.
SAFETY_CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "hospital": [("amenity", "hospital")],
    "police": [("amenity", "police")],
    "consulate": [
        ("diplomatic", "embassy"),
        ("diplomatic", "consulate"),
        ("amenity", "embassy"),
        ("amenity", "consulate"),
    ],
}

# category -> Mapbox Search Box canonical category id. Mapbox's "embassy"
# category also returns consulates in practice (verified live) — there is
# no separate "consulate" category with meaningful coverage.
MAPBOX_CATEGORY_IDS: dict[str, str] = {
    "hospital": "hospital",
    "police": "police",
    "consulate": "embassy",
}


class SafetyAdapterError(Exception):
    """Base class for live safety-resource lookup failures."""


class SafetyAdapterTimeoutError(SafetyAdapterError):
    pass


class SafetyAdapterUnavailableError(SafetyAdapterError):
    pass


class SafetyResourceAdapter(Protocol):
    async def get_nearby_resources(
        self, lat: float, lng: float, radius_km: float, category: str | None
    ) -> list[SafetyResource]: ...


def _categories_for(category: str | None) -> list[str]:
    if category:
        if category not in SAFETY_CATEGORY_TAGS:
            raise ValueError(f"Unknown safety category: {category}")
        return [category]
    return list(SAFETY_CATEGORY_TAGS)


def _build_overpass_query(lat: float, lng: float, radius_m: int, categories: list[str]) -> str:
    # Nodes alone cover the large majority of hospitals/police/consulates
    # and are far cheaper for Overpass to evaluate than also scanning
    # ways; way(around:...) is a comparatively expensive polygon search
    # that measurably increases 504 load-shedding on the public instances
    # for negligible extra coverage on these point-of-interest categories.
    clauses: list[str] = []
    for cat in categories:
        for key, value in SAFETY_CATEGORY_TAGS[cat]:
            clauses.append(f'  node(around:{radius_m},{lat},{lng})["{key}"="{value}"];')
    body = "\n".join(clauses)
    return f"[out:json][timeout:15];\n(\n{body}\n);\nout center;"


def _category_for_tags(tags: dict[str, str]) -> str | None:
    for cat, tag_pairs in SAFETY_CATEGORY_TAGS.items():
        for key, value in tag_pairs:
            if tags.get(key) == value:
                return cat
    return None


def _element_coords(element: dict) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    center = element.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return center["lat"], center["lon"]
    return None


def _format_address(tags: dict[str, str]) -> str | None:
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:city"),
    ]
    joined = " ".join(p for p in parts if p)
    return joined or None


class OSMSafetyResourceAdapter:
    """Real Overpass-backed implementation. Queries the actual traveler
    coordinates and normalizes hospitals/police/consulates from live OSM
    data — never fabricates or hardcodes locations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._limiter = IntervalRateLimiter(settings.safety_resources_min_interval_seconds)
        self._cache: TTLCache[list[SafetyResource]] = TTLCache(settings.safety_resources_cache_ttl_seconds)

    async def _query_one(self, url: str, query: str) -> dict:
        await self._limiter.wait()
        client = get_http_client()
        try:
            response = await client.post(
                url,
                data={"data": query},
                timeout=httpx.Timeout(self._settings.safety_resources_request_timeout_seconds),
            )
        except httpx.TimeoutException as exc:
            raise SafetyAdapterTimeoutError(f"Overpass request to {url} timed out") from exc
        except httpx.HTTPError as exc:
            raise SafetyAdapterUnavailableError(f"Overpass request to {url} failed: {exc}") from exc

        if response.status_code == 429 or response.status_code == 504:
            raise SafetyAdapterUnavailableError(
                f"Overpass at {url} is rate-limiting/load-shedding this client (HTTP {response.status_code})"
            )
        if response.status_code >= 400:
            raise SafetyAdapterUnavailableError(f"Overpass at {url} returned HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise SafetyAdapterUnavailableError(f"Overpass at {url} returned malformed JSON") from exc
        if not isinstance(body, dict):
            raise SafetyAdapterUnavailableError(f"Overpass at {url} returned an unexpected payload shape")
        return body

    async def _query_with_mirrors(self, query: str) -> dict:
        """Try the primary Overpass URL, then each configured mirror in
        order — the public instances load-shed independently, so a
        mirror often succeeds when the primary is 504ing. Only known,
        server-configured URLs are ever used (no user-supplied source,
        preventing SSRF); the last error is raised if every URL fails."""
        urls = [self._settings.safety_resources_base_url, *self._settings.safety_resources_mirror_urls]
        last_error: SafetyAdapterError | None = None
        for url in urls:
            try:
                return await self._query_one(url, query)
            except SafetyAdapterError as exc:
                last_error = exc
                continue
        assert last_error is not None
        raise last_error

    async def get_nearby_resources(
        self, lat: float, lng: float, radius_km: float, category: str | None
    ) -> list[SafetyResource]:
        validate_coordinates(lat, lng)
        categories = _categories_for(category)
        radius_m = int(radius_km * 1000)

        cache_key = f"{round(lat, 3)}:{round(lng, 3)}:{radius_m}:{sorted(categories)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        query = _build_overpass_query(lat, lng, radius_m, categories)
        body = await self._query_with_mirrors(query)

        elements = body.get("elements")
        if not isinstance(elements, list):
            raise SafetyAdapterUnavailableError("Overpass returned an unexpected payload shape")

        retrieved_at = datetime.now(UTC)
        results: list[SafetyResource] = []
        for element in elements:
            if not isinstance(element, dict):
                continue
            coords = _element_coords(element)
            if coords is None:
                continue
            elat, elng = coords
            tags = element.get("tags") or {}
            matched_category = _category_for_tags(tags)
            if matched_category is None or matched_category not in categories:
                continue

            results.append(
                SafetyResource(
                    id=f"osm:{element.get('type', 'node')}:{element.get('id')}",
                    type=matched_category,
                    name=tags.get("name") or f"Unnamed {matched_category}",
                    latitude=elat,
                    longitude=elng,
                    address=_format_address(tags),
                    phone=tags.get("phone") or tags.get("contact:phone"),
                    website=tags.get("website") or tags.get("contact:website"),
                    distance_km=round(haversine_km(lat, lng, elat, elng), 3),
                    source="openstreetmap",
                    is_synthetic=False,
                    retrieved_at=retrieved_at,
                )
            )

        results.sort(key=lambda r: (r.distance_km, r.id))
        self._cache.set(cache_key, results)
        return results


class MapboxSafetyResourceAdapter:
    """Second-tier live implementation using Mapbox's Search Box category
    API — tried only when the free Overpass/mirror chain fails (auto
    mode). Requires MAPBOX_API_KEY; raises SafetyAdapterUnavailableError
    immediately if unset so the caller falls through to seed data rather
    than silently skipping (never a fabricated success)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: TTLCache[list[SafetyResource]] = TTLCache(settings.safety_resources_cache_ttl_seconds)

    async def get_nearby_resources(
        self, lat: float, lng: float, radius_km: float, category: str | None
    ) -> list[SafetyResource]:
        validate_coordinates(lat, lng)
        if not self._settings.mapbox_api_key:
            raise SafetyAdapterUnavailableError("MAPBOX_API_KEY is not configured")

        categories = _categories_for(category)
        cache_key = f"mapbox:{round(lat, 3)}:{round(lng, 3)}:{radius_km}:{sorted(categories)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        retrieved_at = datetime.now(UTC)
        results: list[SafetyResource] = []
        client = get_http_client()

        for cat in categories:
            mapbox_category = MAPBOX_CATEGORY_IDS[cat]
            try:
                response = await client.get(
                    f"{self._settings.mapbox_search_base_url}/{mapbox_category}",
                    params={
                        "access_token": self._settings.mapbox_api_key,
                        "proximity": f"{lng},{lat}",
                        "limit": self._settings.mapbox_search_limit,
                    },
                    timeout=httpx.Timeout(self._settings.mapbox_request_timeout_seconds),
                )
            except httpx.TimeoutException as exc:
                raise SafetyAdapterTimeoutError("Mapbox request timed out") from exc
            except httpx.HTTPError as exc:
                raise SafetyAdapterUnavailableError(f"Mapbox request failed: {exc}") from exc

            if response.status_code == 429:
                raise SafetyAdapterUnavailableError("Mapbox rate-limited this client (HTTP 429)")
            if response.status_code >= 400:
                raise SafetyAdapterUnavailableError(f"Mapbox returned HTTP {response.status_code}")

            try:
                body = response.json()
            except ValueError as exc:
                raise SafetyAdapterUnavailableError("Mapbox returned malformed JSON") from exc
            if not isinstance(body, dict):
                raise SafetyAdapterUnavailableError("Mapbox returned an unexpected payload shape")

            features = body.get("features")
            if not isinstance(features, list):
                raise SafetyAdapterUnavailableError("Mapbox returned an unexpected payload shape")

            for feature in features:
                if not isinstance(feature, dict):
                    continue
                geometry = feature.get("geometry") or {}
                coords = geometry.get("coordinates")
                if not isinstance(coords, list) or len(coords) != 2:
                    continue
                flng, flat = coords
                props = feature.get("properties") or {}
                metadata = props.get("metadata") or {}
                mapbox_id = props.get("mapbox_id") or f"{flat}:{flng}"

                dist_km = (
                    round(props["distance"] / 1000.0, 3)
                    if isinstance(props.get("distance"), (int, float))
                    else round(haversine_km(lat, lng, flat, flng), 3)
                )

                results.append(
                    SafetyResource(
                        id=f"mapbox:{mapbox_id}",
                        type=cat,
                        name=props.get("name") or f"Unnamed {cat}",
                        latitude=flat,
                        longitude=flng,
                        address=props.get("full_address") or props.get("place_formatted"),
                        phone=metadata.get("phone"),
                        website=metadata.get("website"),
                        distance_km=dist_km,
                        source="mapbox",
                        is_synthetic=False,
                        retrieved_at=retrieved_at,
                    )
                )

        # Mapbox's distance is straight-line from the query point, not
        # bounded by radius_km server-side — apply the same radius
        # contract the other adapters honor.
        results = [r for r in results if r.distance_km is not None and r.distance_km <= radius_km]
        results.sort(key=lambda r: (r.distance_km, r.id))
        self._cache.set(cache_key, results)
        return results


class SeedSafetyResourceAdapter:
    """Deterministic, clearly-labelled fallback — never presented as live
    (`is_synthetic=True`, `source="seed_fallback"`). Positions are offset
    from the given coordinates so the demo still shows *something* nearby
    when the live provider fails, but this is never the default path."""

    async def get_nearby_resources(
        self, lat: float, lng: float, radius_km: float, category: str | None
    ) -> list[SafetyResource]:
        validate_coordinates(lat, lng)
        seed_data = [
            {"id": "seed:h1", "type": "hospital", "name": "General City Hospital", "latitude": lat + 0.01, "longitude": lng + 0.01, "address": "123 Health Ave", "phone": "555-0100"},
            {"id": "seed:h2", "type": "hospital", "name": "Mercy Clinic", "latitude": lat - 0.02, "longitude": lng - 0.01, "address": "456 Healing Blvd", "phone": "555-0101"},
            {"id": "seed:p1", "type": "police", "name": "Central Precinct", "latitude": lat + 0.015, "longitude": lng - 0.005, "address": "789 Justice St", "phone": "555-0200"},
            {"id": "seed:c1", "type": "consulate", "name": "Embassy of Global Alliance", "latitude": lat - 0.005, "longitude": lng + 0.02, "address": "10 Diplomat Rd", "phone": "555-0300"},
        ]

        retrieved_at = datetime.now(UTC)
        results: list[SafetyResource] = []
        for d in seed_data:
            if category and category != d["type"]:
                continue

            dist = haversine_km(lat, lng, d["latitude"], d["longitude"])
            if dist <= radius_km:
                results.append(
                    SafetyResource(
                        id=d["id"],
                        type=d["type"],
                        name=d["name"],
                        latitude=d["latitude"],
                        longitude=d["longitude"],
                        address=d["address"],
                        phone=d["phone"],
                        website=None,
                        distance_km=round(dist, 3),
                        source="seed_fallback",
                        is_synthetic=True,
                        retrieved_at=retrieved_at,
                    )
                )

        results.sort(key=lambda r: (r.distance_km, r.id))
        return results


__all__ = [
    "MapboxSafetyResourceAdapter",
    "OSMSafetyResourceAdapter",
    "SafetyAdapterError",
    "SafetyAdapterTimeoutError",
    "SafetyAdapterUnavailableError",
    "SafetyResourceAdapter",
    "SeedSafetyResourceAdapter",
    "SAFETY_CATEGORY_TAGS",
    "MAPBOX_CATEGORY_IDS",
]
