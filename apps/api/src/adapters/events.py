"""EventAdapter — real implementation using the Ticketmaster Discovery
API v2 (Phase 9).

GET https://app.ticketmaster.com/discovery/v2/events.json — location-
based discovery via `latlong`+`radius`, date filtering via
`startDateTime`/`endDateTime` (ISO-8601 UTC, 'Z' suffix), category
filtering via `classificationName`, server-side `apikey` query param.
Same adapter pattern as src/adapters/routing.py/geocoding.py: shared
httpx client, IntervalRateLimiter, TTLCache, typed error hierarchy.

Status normalization is conservative: Ticketmaster's `dates.status.code`
field (`onsale`/`offsale`/`cancelled`/`postponed`/`rescheduled`) is the
ONLY source of ExternalEventStatus — a missing/unrecognized code is
UNKNOWN, never inferred as cancelled. Ticketmaster being unreachable is
EVENT_CONTEXT_UNAVAILABLE (raised as AdapterUnavailableError for the
caller to translate), never EVENT_CANCELLED for any existing event.

Fallback: SeedEventAdapter for tests/dev — every event it returns is
`is_synthetic=True`, `source="seed"`. An empty live result is a valid,
reportable state (0 events) and is never replaced with fabricated data.

NOT VERIFIED against the live Ticketmaster API in this worktree — no API
key is available here. Verified only via unit tests against a fake HTTP
client (tests/test_event_adapter.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

import httpx

from src.adapters.errors import AdapterRateLimitedError, AdapterUnavailableError
from src.core.cache import TTLCache
from src.core.config import Settings
from src.core.http_client import get_http_client
from src.core.rate_limit import IntervalRateLimiter


class ExternalEventStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"
    UNKNOWN = "UNKNOWN"


_STATUS_MAP = {
    "onsale": ExternalEventStatus.SCHEDULED,
    "offsale": ExternalEventStatus.SCHEDULED,
    "cancelled": ExternalEventStatus.CANCELLED,
    "postponed": ExternalEventStatus.POSTPONED,
    "rescheduled": ExternalEventStatus.RESCHEDULED,
}


@dataclass(frozen=True)
class ExternalEvent:
    """Normalized event context — kept distinct from the Experience
    domain model on purpose (docs/AI_CONTEXT.md: events are candidate
    context, not catalog items, until an explicit approved transform)."""

    id: str
    external_event_id: str
    source: str  # "ticketmaster" | "seed"
    name: str
    description: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    status: ExternalEventStatus
    venue_name: str | None
    venue_address: str | None
    latitude: float | None
    longitude: float | None
    category: str | None
    image_url: str | None
    purchase_url: str | None
    source_url: str | None
    source_confidence: float | None
    source_updated_at: datetime | None
    fetched_at: datetime
    expires_at: datetime
    is_synthetic: bool


class EventAdapter(Protocol):
    async def search_events(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        category: str | None = None,
    ) -> list[ExternalEvent]: ...


def _parse_status(raw: dict[str, Any] | None) -> ExternalEventStatus:
    if not raw:
        return ExternalEventStatus.UNKNOWN
    status_block = raw.get("status") or {}
    code = status_block.get("code")
    if not isinstance(code, str):
        return ExternalEventStatus.UNKNOWN
    return _STATUS_MAP.get(code.lower(), ExternalEventStatus.UNKNOWN)


def _parse_datetime(dates: dict[str, Any] | None, key: str) -> datetime | None:
    if not dates:
        return None
    start_block = dates.get(key) or {}
    date_time = start_block.get("dateTime")
    if isinstance(date_time, str):
        try:
            return datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_event(raw: dict[str, Any], *, fetched_at: datetime, ttl_seconds: float) -> ExternalEvent | None:
    event_id = raw.get("id")
    name = raw.get("name")
    if not isinstance(event_id, str) or not isinstance(name, str):
        return None  # malformed record — skip rather than fabricate fields

    dates = raw.get("dates") or {}
    starts_at = _parse_datetime(dates, "start")
    ends_at = _parse_datetime(dates, "end")

    venues = ((raw.get("_embedded") or {}).get("venues")) or []
    venue = venues[0] if venues else {}
    address_block = venue.get("address") or {}
    location_block = venue.get("location") or {}
    lat = location_block.get("latitude")
    lng = location_block.get("longitude")

    classifications = raw.get("classifications") or []
    classification0 = classifications[0] if classifications else {}
    segment = classification0.get("segment") or {}
    category = segment.get("name")

    images = raw.get("images") or []
    image_url = images[0].get("url") if images and isinstance(images[0], dict) else None

    updated_raw = raw.get("locale")  # placeholder; Ticketmaster doesn't
    # give a reliable single "record updated" timestamp on the public
    # Discovery API — left None rather than guessed from an unrelated field.
    _ = updated_raw

    return ExternalEvent(
        id=event_id,
        external_event_id=event_id,
        source="ticketmaster",
        name=name,
        description=raw.get("info") or raw.get("pleaseNote"),
        starts_at=starts_at,
        ends_at=ends_at,
        status=_parse_status(dates),
        venue_name=venue.get("name"),
        venue_address=address_block.get("line1"),
        latitude=float(lat) if isinstance(lat, (int, float, str)) and lat not in (None, "") else None,
        longitude=float(lng) if isinstance(lng, (int, float, str)) and lng not in (None, "") else None,
        category=category,
        image_url=image_url,
        purchase_url=raw.get("url"),
        source_url=raw.get("url"),
        source_confidence=0.9,
        source_updated_at=None,
        fetched_at=fetched_at,
        expires_at=datetime.fromtimestamp(fetched_at.timestamp() + ttl_seconds, tz=UTC),
        is_synthetic=False,
    )


class SeedEventAdapter:
    """Deterministic, no-network fallback for tests/dev. Every event
    carries is_synthetic=True, source="seed" — never mistaken for a live
    Ticketmaster result."""

    async def search_events(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        category: str | None = None,
    ) -> list[ExternalEvent]:
        # Deliberately returns an empty list — a mock/seed adapter must
        # never invent a plausible-looking live event; if seed fixtures
        # are needed for a specific test, that test constructs its own
        # ExternalEvent instances directly rather than relying on this
        # adapter to guess demo content.
        return []


class TicketmasterEventAdapter:
    """Real Ticketmaster Discovery API v2 adapter.

    GET https://app.ticketmaster.com/discovery/v2/events.json
        ?apikey={key}&latlong={lat},{lng}&radius={km}&unit=km
        &startDateTime=...&endDateTime=...&classificationName=...

    401/403 -> AdapterUnavailableError (invalid/missing key).
    429 -> AdapterRateLimitedError. 5xx/timeout/malformed JSON ->
    AdapterUnavailableError. A successful response with zero results is
    a valid, cacheable outcome — returned as an empty list, never as an
    error and never backfilled with synthetic data.
    """

    _BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._limiter = IntervalRateLimiter(settings.events_min_interval_seconds)
        self._cache: TTLCache[list[ExternalEvent]] = TTLCache(settings.events_cache_ttl_seconds)

    def _cache_key(
        self, lat: float, lng: float, radius_m: int, start: datetime | None, end: datetime | None, category: str | None
    ) -> str:
        bucket = int(time.time() // max(1, int(self._settings.events_cache_ttl_seconds)))
        return (
            f"{round(lat, 2)}:{round(lng, 2)}:{radius_m}:"
            f"{start.isoformat() if start else ''}:{end.isoformat() if end else ''}:"
            f"{category or ''}:{bucket}"
        )

    async def search_events(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        category: str | None = None,
    ) -> list[ExternalEvent]:
        if not self._settings.ticketmaster_api_key:
            raise AdapterUnavailableError("TICKETMASTER_API_KEY is not configured.")

        key = self._cache_key(lat, lng, radius_m, start, end, category)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        await self._limiter.wait()
        client = get_http_client()
        params: dict[str, Any] = {
            "apikey": self._settings.ticketmaster_api_key,
            "latlong": f"{lat},{lng}",
            "radius": max(1, round(radius_m / 1000)),
            "unit": "km",
            "size": 50,
        }
        if start is not None:
            params["startDateTime"] = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if end is not None:
            params["endDateTime"] = end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if category:
            params["classificationName"] = category

        try:
            response = await client.get(
                self._BASE_URL,
                params=params,
                timeout=httpx.Timeout(self._settings.events_request_timeout_seconds),
            )
        except httpx.TimeoutException as exc:
            raise AdapterUnavailableError("Ticketmaster request timed out") from exc
        except httpx.HTTPError as exc:
            raise AdapterUnavailableError(f"Ticketmaster request failed: {exc}") from exc

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise AdapterRateLimitedError(
                "Ticketmaster rate limit exceeded",
                retry_after_seconds=float(retry_after) if retry_after else None,
            )
        if response.status_code in (401, 403):
            raise AdapterUnavailableError(f"Ticketmaster authorization failed (HTTP {response.status_code})")
        if response.status_code == 404:
            # Ticketmaster's own documented behavior for "no results in a
            # bounded search" in some parameter combinations — a valid
            # empty result, not an error.
            self._cache.set(key, [])
            return []
        if response.status_code >= 500:
            raise AdapterUnavailableError(f"Ticketmaster returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AdapterUnavailableError(f"Ticketmaster returned HTTP {response.status_code}")

        try:
            body: dict[str, Any] = response.json()
        except ValueError as exc:
            raise AdapterUnavailableError("Ticketmaster returned malformed JSON") from exc
        if not isinstance(body, dict):
            raise AdapterUnavailableError("Ticketmaster returned an unexpected payload shape")

        raw_events = ((body.get("_embedded") or {}).get("events")) or []
        fetched_at = datetime.now(UTC)
        events = [
            parsed
            for raw in raw_events
            if isinstance(raw, dict)
            and (parsed := _parse_event(raw, fetched_at=fetched_at, ttl_seconds=self._settings.events_cache_ttl_seconds))
            is not None
        ]
        self._cache.set(key, events)
        return events


__all__ = [
    "EventAdapter",
    "ExternalEvent",
    "ExternalEventStatus",
    "SeedEventAdapter",
    "TicketmasterEventAdapter",
]
