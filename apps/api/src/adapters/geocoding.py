"""GeocodingAdapter interface — Nominatim.

Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/):
  - max 1 request/second from this application, self-enforced
  - a descriptive User-Agent identifying the app (not a browser UA)
  - attribution: "© OpenStreetMap contributors"
  - autocomplete/type-ahead and bulk/systematic querying are explicitly
    prohibited — this adapter is only ever called from an explicit-submit
    search or reverse-geocode action, never on every keystroke

See docs/DECISIONS.md ADR-022.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from src.adapters.errors import AdapterRateLimitedError, AdapterUnavailableError
from src.core.cache import TTLCache
from src.core.config import Settings
from src.core.http_client import get_http_client
from src.core.rate_limit import IntervalRateLimiter


@dataclass(frozen=True)
class LocationResult:
    display_name: str
    lat: float
    lng: float
    city: str | None
    locality: str | None
    state: str | None
    country: str | None
    source: str = "nominatim"


class GeocodingAdapter(Protocol):
    async def search(self, query: str, *, limit: int = 5) -> list[LocationResult]: ...

    async def reverse(self, lat: float, lng: float) -> LocationResult | None: ...


class MockGeocodingAdapter:
    """Used when Nominatim is disabled/unreachable. Returns nothing rather
    than fabricating a plausible-looking location."""

    async def search(self, query: str, *, limit: int = 5) -> list[LocationResult]:
        return []

    async def reverse(self, lat: float, lng: float) -> LocationResult | None:
        return None


def _normalize_nominatim_item(item: dict[str, Any]) -> LocationResult:
    address = item.get("address") or {}
    city = address.get("city") or address.get("town") or address.get("village")
    locality = address.get("suburb") or address.get("neighbourhood") or address.get("locality")
    return LocationResult(
        display_name=item.get("display_name", ""),
        lat=float(item["lat"]),
        lng=float(item["lon"]),
        city=city,
        locality=locality,
        state=address.get("state"),
        country=address.get("country"),
        source="nominatim",
    )


class NominatimGeocodingAdapter:
    """Real Nominatim-backed implementation, rate-limited and cached."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._limiter = IntervalRateLimiter(settings.nominatim_min_interval_seconds)
        self._search_cache: TTLCache[list[LocationResult]] = TTLCache(settings.nominatim_cache_ttl_seconds)
        self._reverse_cache: TTLCache[LocationResult | None] = TTLCache(settings.nominatim_cache_ttl_seconds)

    async def _get(self, path: str, params: dict[str, Any]) -> httpx.Response:
        await self._limiter.wait()
        client = get_http_client()
        try:
            response = await client.get(
                f"{self._settings.nominatim_base_url}{path}",
                params=params,
                headers={"User-Agent": self._settings.nominatim_user_agent},
            )
        except httpx.TimeoutException as exc:
            raise AdapterUnavailableError("Nominatim request timed out") from exc
        except httpx.HTTPError as exc:
            raise AdapterUnavailableError(f"Nominatim request failed: {exc}") from exc

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise AdapterRateLimitedError(
                "Nominatim rate limit exceeded", retry_after_seconds=float(retry_after) if retry_after else None
            )
        if response.status_code >= 400:
            raise AdapterUnavailableError(f"Nominatim returned HTTP {response.status_code}")
        return response

    async def search(self, query: str, *, limit: int = 5) -> list[LocationResult]:
        normalized_query = " ".join(query.strip().lower().split())
        if not normalized_query:
            return []
        cache_key = f"search:{normalized_query}:{limit}"

        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(
            "/search",
            {"q": normalized_query, "format": "jsonv2", "addressdetails": 1, "limit": limit},
        )
        try:
            items = response.json()
        except ValueError as exc:
            raise AdapterUnavailableError("Nominatim returned malformed JSON") from exc

        results = [_normalize_nominatim_item(item) for item in items]
        self._search_cache.set(cache_key, results)
        return results

    async def reverse(self, lat: float, lng: float) -> LocationResult | None:
        # Round to ~11m precision for cache-key stability without
        # materially affecting result quality.
        cache_key = f"reverse:{round(lat, 4)}:{round(lng, 4)}"
        cached = self._reverse_cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(
            "/reverse", {"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1}
        )
        try:
            item = response.json()
        except ValueError as exc:
            raise AdapterUnavailableError("Nominatim returned malformed JSON") from exc

        if not item or "lat" not in item:
            self._reverse_cache.set(cache_key, None)
            return None

        result = _normalize_nominatim_item(item)
        self._reverse_cache.set(cache_key, result)
        return result


__all__ = [
    "GeocodingAdapter",
    "LocationResult",
    "MockGeocodingAdapter",
    "NominatimGeocodingAdapter",
]
