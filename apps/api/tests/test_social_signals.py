from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx

from src.adapters import social_signals as social_adapter_module
from src.adapters.geocoding import LocationResult
from src.adapters.social_signals import (
    BlueskySocialSignalAdapter,
    KeywordSocialSignalInterpreter,
    NormalizedSocialSignal,
    SocialSeverity,
    SocialTopic,
)
from src.core.config import Settings
from src.core.social_signals import get_social_signal_service
from src.schemas.social_signals import SocialSignalsResponse
from src.services.social_signal_aggregation import aggregate_social_signals
from src.services.social_signals import SocialSignalService
from tests.conftest import auth_header, register_traveler


def signal(
    index: int,
    *,
    topic: SocialTopic = SocialTopic.FLOODING,
    minutes_ago: int = 20,
    author: str | None = None,
) -> NormalizedSocialSignal:
    return NormalizedSocialSignal(
        deduplication_key=f"post-{index:016d}",
        source_fingerprint=author or f"author-{index:016d}",
        topic=topic,
        severity=SocialSeverity.HIGH if index % 2 else SocialSeverity.MODERATE,
        occurred_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        classification_confidence=0.68,
    )


def test_keyword_interpreter_uses_small_deterministic_taxonomy() -> None:
    interpreter = KeywordSocialSignalInterpreter()
    flood = interpreter.interpret("Mumbai waterlogging has stranded commuters")
    assert flood is not None
    assert flood.topic is SocialTopic.FLOODING
    assert flood.severity is SocialSeverity.HIGH
    assert interpreter.interpret("Theatre tickets are on sale") is None


def test_bluesky_adapter_normalizes_and_discards_raw_post_fields(monkeypatch) -> None:
    now = datetime.now(UTC).isoformat()

    class FakeClient:
        async def get(self, url, *, params, timeout, headers):
            assert url == BlueskySocialSignalAdapter.BASE_URL
            assert params == {"q": "Mumbai", "sort": "latest", "limit": 100}
            posts = [
                {
                    "uri": "at://did:plc:secret/app.bsky.feed.post/first",
                    "record": {"text": "Mumbai roads waterlogged after rain", "createdAt": now},
                    "author": {"did": "did:plc:secret", "handle": "private.example"},
                    "indexedAt": now,
                },
                {
                    "uri": "at://did:plc:another/app.bsky.feed.post/second",
                    "record": {"text": "Mumbai roads waterlogged after rain", "createdAt": now},
                    "author": {"did": "did:plc:another", "handle": "other.example"},
                    "indexedAt": now,
                },
                {
                    "uri": "at://did:plc:other/app.bsky.feed.post/third",
                    "record": {"text": "Mumbai concert postponed", "createdAt": now},
                    "author": {"did": "did:plc:other", "handle": "third.example"},
                    "indexedAt": now,
                },
            ]
            return httpx.Response(
                200,
                json={"posts": posts},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(social_adapter_module, "get_http_client", lambda: FakeClient())
    adapter = BlueskySocialSignalAdapter(Settings(social_signal_min_interval_seconds=0))
    normalized = asyncio.run(
        adapter.search(
            "Mumbai",
            ["Mumbai"],
            center_latitude=19.0,
            center_longitude=72.0,
            since=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    # Duplicate text is retained as independent observations for aggregation;
    # only provider identity within each row is represented as a salted hash.
    assert len(normalized) == 3
    assert normalized[0].topic is SocialTopic.FLOODING
    assert normalized[1].source_fingerprint != normalized[0].source_fingerprint
    assert all("text" not in item.model_dump() and "handle" not in item.model_dump() for item in normalized)


def test_aggregation_is_bounded_and_reports_sparse_trend_honestly() -> None:
    now = datetime.now(UTC)
    clusters = aggregate_social_signals(
        [signal(1), signal(2), signal(3, minutes_ago=220)],
        area_name="Fort",
        latitude=18.93,
        longitude=72.83,
        half_life_hours=6,
        now=now,
    )
    assert len(clusters) == 1
    assert clusters[0].location_precision == "area"
    assert clusters[0].signal_count == 3
    assert clusters[0].independent_source_count == 3
    assert clusters[0].trend == "insufficient_data"
    assert 0 <= clusters[0].confidence <= 1


class FakeGeocoder:
    def __init__(self):
        self.calls = 0

    async def reverse(self, lat: float, lng: float):
        self.calls += 1
        return LocationResult("Fort, Mumbai", lat, lng, "Mumbai", "Fort", "Maharashtra", "India")

    async def search(self, query: str, *, limit: int = 5):
        return []


class FakeAdapter:
    def __init__(self):
        self.calls = 0

    async def search(self, area_name, aliases, *, center_latitude, center_longitude, since):
        self.calls += 1
        return [signal(1)]


def test_service_uses_verified_area_and_caches_aggregate_only() -> None:
    geocoder = FakeGeocoder()
    adapter = FakeAdapter()
    service = SocialSignalService(Settings(social_signal_cache_ttl_seconds=60), geocoder, adapter)

    async def load_twice():
        first = await service.get_social_signals(18.93, 72.83, 10)
        second = await service.get_social_signals(18.93, 72.83, 10)
        return first, second

    first, second = asyncio.run(load_twice())
    assert first.status == "AVAILABLE"
    assert first.queried_location == "Fort"
    response_json = first.model_dump_json()
    assert "source_fingerprint" not in response_json
    assert "deduplication_key" not in response_json
    assert adapter.calls == 1
    assert geocoder.calls == 1
    assert second == first

    async def load_many_centers():
        for index in range(70):
            await service.get_social_signals(18.93 + (index / 100_000), 72.83, 10)

    asyncio.run(load_many_centers())
    assert len(service._cache) == 64


def test_social_signal_endpoint_requires_auth_and_rejects_bad_coordinates(client) -> None:
    assert client.get("/api/v1/twin/social-signals?lat=18.93&lng=72.83").status_code == 401
    traveler = register_traveler(client, "social-signals@example.com")
    response = client.get(
        "/api/v1/twin/social-signals?lat=91&lng=72.83",
        headers=auth_header(traveler),
    )
    assert response.status_code == 422


def test_social_signal_endpoint_returns_aggregates_only(client) -> None:
    traveler = register_traveler(client, "social-aggregate@example.com")
    response_model = SocialSignalsResponse(
        status="NO_SIGNALS",
        radius_km=10,
        generated_at=datetime.now(UTC),
        clusters=[],
        message="No matching posts.",
    )

    captured: dict[str, object] = {}

    class EmptyService:
        async def get_social_signals(self, lat, lng, radius, topics, since_hours):
            captured.update(lat=lat, lng=lng, radius=radius, topics=topics, since_hours=since_hours)
            return response_model

    client.app.dependency_overrides[get_social_signal_service] = lambda: EmptyService()
    response = client.get(
        "/api/v1/twin/social-signals?lat=18.93&lng=72.83&topics=flooding&since_hours=6",
        headers=auth_header(traveler),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NO_SIGNALS"
    assert captured == {"lat": 18.93, "lng": 72.83, "radius": 10, "topics": ["flooding"], "since_hours": 6}
    assert "post_text" not in response.text
    assert "author_did" not in response.text
    client.app.dependency_overrides.pop(get_social_signal_service, None)


def test_social_signal_endpoint_rejects_unsupported_lookback(client) -> None:
    traveler = register_traveler(client, "social-lookback@example.com")
    response = client.get(
        "/api/v1/twin/social-signals?lat=18.93&lng=72.83&since_hours=25",
        headers=auth_header(traveler),
    )
    assert response.status_code == 422
