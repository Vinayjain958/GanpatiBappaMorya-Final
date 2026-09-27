"""Bounded orchestration for optional public social context."""

from __future__ import annotations

import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import Literal

from src.adapters.geocoding import GeocodingAdapter
from src.adapters.social_signals import (
    BlueskySocialSignalAdapter,
    SocialSignalRateLimitedError,
    SocialSignalUnavailableError,
    SocialTopic,
)
from src.core.config import Settings
from src.schemas.social_signals import SocialSignalsResponse
from src.services.social_signal_aggregation import aggregate_social_signals

_ALL_TOPICS = frozenset(topic.value for topic in SocialTopic)
_MAX_CACHE_ENTRIES = 64


class SocialSignalService:
    def __init__(
        self,
        settings: Settings,
        geocoder: GeocodingAdapter,
        adapter: BlueskySocialSignalAdapter,
    ) -> None:
        self._settings = settings
        self._geocoder = geocoder
        self._adapter = adapter
        self._cache: OrderedDict[str, tuple[float, SocialSignalsResponse]] = OrderedDict()
        self._stale: dict[str, tuple[datetime, SocialSignalsResponse]] = {}

    async def get_social_signals(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        topics: list[str] | None = None,
        since_hours: int | None = None,
    ) -> SocialSignalsResponse:
        selected_topics = set(topics or [])
        if selected_topics - _ALL_TOPICS:
            raise ValueError("One or more social-signal topics are not supported")
        lookback_hours = since_hours if since_hours is not None else self._settings.social_signal_lookback_hours
        if lookback_hours < 1 or lookback_hours > self._settings.social_signal_lookback_hours:
            raise ValueError("since_hours must be within the configured social-signal lookback window")
        key = (
            f"{latitude:.6f}:{longitude:.6f}:{radius_km:.1f}:{lookback_hours}:"
            f"{','.join(sorted(selected_topics))}"
        )
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        now = datetime.now(UTC)
        if not self._settings.social_signals_enabled:
            return self._empty(
                "UNAVAILABLE",
                radius_km,
                now,
                "Public social context is disabled in this environment.",
            )

        try:
            place = await self._geocoder.reverse(latitude, longitude)
        except Exception:  # noqa: BLE001 — optional context must degrade safely
            place = None
        if place is None:
            return self._stale_or_empty(
                key,
                "UNAVAILABLE",
                radius_km,
                now,
                "This area could not be verified by the existing location service. No social map markers were added.",
            )

        area_name = place.locality or place.city
        if not area_name or len(area_name.strip()) < 2:
            return self._stale_or_empty(
                key,
                "UNAVAILABLE",
                radius_km,
                now,
                "The selected area has no verified locality name. No social map markers were added.",
            )
        aliases = [name for name in (place.locality, place.city) if name]

        try:
            normalized = await self._adapter.search(
                area_name,
                aliases,
                center_latitude=latitude,
                center_longitude=longitude,
                since=now - timedelta(hours=lookback_hours),
            )
        except SocialSignalRateLimitedError:
            return self._stale_or_empty(
                key,
                "RATE_LIMITED",
                radius_km,
                now,
                "Bluesky public search is temporarily rate-limited. Try again later.",
                area_name,
            )
        except SocialSignalUnavailableError:
            return self._stale_or_empty(
                key,
                "UNAVAILABLE",
                radius_km,
                now,
                "Bluesky public search is temporarily unavailable.",
                area_name,
            )

        if selected_topics:
            normalized = [signal for signal in normalized if signal.topic.value in selected_topics]
        clusters = aggregate_social_signals(
            normalized,
            area_name=area_name,
            # These are the user's selected map/search coordinates, not
            # coordinates claimed by any Bluesky post.
            latitude=latitude,
            longitude=longitude,
            half_life_hours=self._settings.social_signal_confidence_half_life_hours,
            now=now,
        )
        message = (
            "No matching public posts were found for this verified area in the recent Bluesky search window. "
            "That does not establish that the area has no disruption."
            if not clusters
            else (
                "Area-level public social signals. Posts are not geotagged here; map markers show the selected "
                "search center, not a post location. The radius is a map context setting, not a verified "
                "per-post distance filter."
            )
        )
        response = SocialSignalsResponse(
            status="AVAILABLE" if clusters else "NO_SIGNALS",
            queried_location=area_name,
            radius_km=radius_km,
            generated_at=now,
            clusters=clusters,
            message=message,
        )
        self._remember_cache(key, response)
        self._remember_stale(key, response, now)
        return response

    def _get_cached(self, key: str) -> SocialSignalsResponse | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        expires_at, response = cached
        if expires_at <= time.monotonic():
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return response

    def _remember_cache(self, key: str, response: SocialSignalsResponse) -> None:
        self._cache[key] = (time.monotonic() + self._settings.social_signal_cache_ttl_seconds, response)
        self._cache.move_to_end(key)
        while len(self._cache) > _MAX_CACHE_ENTRIES:
            self._cache.popitem(last=False)

    def _stale_or_empty(
        self,
        key: str,
        status: Literal["AVAILABLE", "NO_SIGNALS", "UNAVAILABLE", "RATE_LIMITED", "STALE"],
        radius_km: float,
        now: datetime,
        message: str,
        area_name: str | None = None,
    ) -> SocialSignalsResponse:
        fallback = self._stale.get(key)
        if fallback is not None and now - fallback[0] <= timedelta(hours=2):
            previous = fallback[1]
            return previous.model_copy(
                update={
                    "status": "STALE",
                    "message": (
                        "Showing a cached aggregate because the provider could not refresh it. "
                        f"{message} Previous query: {previous.message}"
                    ),
                }
            )
        return self._empty(status, radius_km, now, message, area_name)

    def _remember_stale(self, key: str, response: SocialSignalsResponse, now: datetime) -> None:
        self._stale[key] = (now, response)
        if len(self._stale) > 32:
            oldest_key = min(self._stale, key=lambda entry: self._stale[entry][0])
            del self._stale[oldest_key]

    @staticmethod
    def _empty(
        status: Literal["AVAILABLE", "NO_SIGNALS", "UNAVAILABLE", "RATE_LIMITED", "STALE"],
        radius_km: float,
        now: datetime,
        message: str,
        area_name: str | None = None,
    ) -> SocialSignalsResponse:
        return SocialSignalsResponse(
            status=status,
            queried_location=area_name,
            radius_km=radius_km,
            generated_at=now,
            clusters=[],
            message=message,
        )


__all__ = ["SocialSignalService"]
