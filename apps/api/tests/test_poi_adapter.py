from __future__ import annotations

import asyncio

import pytest

from src.adapters.errors import AdapterRateLimitedError
from src.adapters.poi import OverpassPOIAdapter
from src.core.config import Settings
from tests.adapter_fakes import FakeAsyncClient, make_response, sequence_responder

OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 123,
            "lat": 18.935,
            "lon": 72.836,
            "tags": {"name": "Sample Cafe", "amenity": "cafe"},
        },
        {
            "type": "way",  # not a node — must be filtered out (no direct lat/lon)
            "id": 456,
            "tags": {"name": "Some Building"},
        },
    ]
}


def _settings() -> Settings:
    return Settings(overpass_min_interval_seconds=0.0)


def _install_fake_client(monkeypatch, fake: FakeAsyncClient) -> None:
    monkeypatch.setattr("src.adapters.poi.get_http_client", lambda: fake)


def test_query_construction_is_deterministic() -> None:
    from src.adapters.poi import _build_overpass_query

    query = _build_overpass_query(18.93, 72.83, 500, ["cafe"])
    assert 'node(around:500,18.93,72.83)["amenity"="cafe"];' in query
    assert query == _build_overpass_query(18.93, 72.83, 500, ["cafe"])  # deterministic


def test_unknown_category_rejected() -> None:
    adapter = OverpassPOIAdapter(_settings())
    with pytest.raises(ValueError):
        asyncio.run(adapter.search_nearby(18.93, 72.83, 500, ["not-a-real-category"]))


def test_radius_over_configured_max_rejected() -> None:
    settings = _settings()
    adapter = OverpassPOIAdapter(settings)
    with pytest.raises(ValueError):
        asyncio.run(
            adapter.search_nearby(18.93, 72.83, settings.overpass_max_radius_m + 1, ["cafe"])
        )


def test_response_normalization(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, fake)

    adapter = OverpassPOIAdapter(_settings())
    results = asyncio.run(adapter.search_nearby(18.93, 72.83, 500, ["cafe"]))

    assert len(results) == 1  # the "way" element without lat/lon is dropped
    assert results[0].name == "Sample Cafe"
    assert results[0].osm_type == "node"
    assert results[0].osm_id == 123
    assert results[0].distance_km >= 0


def test_rate_limit_response_raises_typed_error(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(429, headers={"Retry-After": "5"})]))
    _install_fake_client(monkeypatch, fake)

    adapter = OverpassPOIAdapter(_settings())
    with pytest.raises(AdapterRateLimitedError):
        asyncio.run(adapter.search_nearby(18.93, 72.83, 500, ["cafe"]))


def test_results_are_cached(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, fake)

    adapter = OverpassPOIAdapter(_settings())

    async def _twice() -> None:
        await adapter.search_nearby(18.93, 72.83, 500, ["cafe"])
        await adapter.search_nearby(18.93, 72.83, 500, ["cafe"])

    asyncio.run(_twice())
    assert len(fake.calls) == 1


def test_no_categories_returns_empty_without_request(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, fake)

    adapter = OverpassPOIAdapter(_settings())
    results = asyncio.run(adapter.search_nearby(18.93, 72.83, 500, []))

    assert results == []
    assert len(fake.calls) == 0
