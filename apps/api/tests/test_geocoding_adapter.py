from __future__ import annotations

import asyncio

import httpx
import pytest

from src.adapters.errors import AdapterRateLimitedError, AdapterUnavailableError
from src.adapters.geocoding import NominatimGeocodingAdapter
from src.core.config import Settings
from tests.adapter_fakes import FakeAsyncClient, make_response, sequence_responder

NOMINATIM_SEARCH_ITEM = {
    "display_name": "Fort, Mumbai, Maharashtra, India",
    "lat": "18.9346",
    "lon": "72.8356",
    "address": {"suburb": "Fort", "city": "Mumbai", "state": "Maharashtra", "country": "India"},
}


def _settings() -> Settings:
    return Settings(nominatim_min_interval_seconds=0.0)


def _install_fake_client(monkeypatch, fake: FakeAsyncClient) -> None:
    monkeypatch.setattr("src.adapters.geocoding.get_http_client", lambda: fake)


def test_search_normalizes_response(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, [NOMINATIM_SEARCH_ITEM])]))
    _install_fake_client(monkeypatch, fake)

    adapter = NominatimGeocodingAdapter(_settings())
    results = asyncio.run(adapter.search("Fort Mumbai"))

    assert len(results) == 1
    assert results[0].display_name == "Fort, Mumbai, Maharashtra, India"
    assert results[0].lat == 18.9346
    assert results[0].lng == 72.8356
    assert results[0].city == "Mumbai"
    assert results[0].locality == "Fort"
    assert results[0].source == "nominatim"


def test_reverse_normalizes_response(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, NOMINATIM_SEARCH_ITEM)]))
    _install_fake_client(monkeypatch, fake)

    adapter = NominatimGeocodingAdapter(_settings())
    result = asyncio.run(adapter.reverse(18.9346, 72.8356))

    assert result is not None
    assert result.city == "Mumbai"


def test_reverse_handles_empty_result(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, {})]))
    _install_fake_client(monkeypatch, fake)

    adapter = NominatimGeocodingAdapter(_settings())
    result = asyncio.run(adapter.reverse(0, 0))

    assert result is None


def test_search_raises_on_timeout(monkeypatch) -> None:
    def _raise(**_kwargs: object) -> None:
        raise httpx.TimeoutException("timed out")

    fake = FakeAsyncClient(_raise)
    _install_fake_client(monkeypatch, fake)

    adapter = NominatimGeocodingAdapter(_settings())
    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search("Fort"))


def test_search_raises_on_429(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(429, headers={"Retry-After": "2"})]))
    _install_fake_client(monkeypatch, fake)

    adapter = NominatimGeocodingAdapter(_settings())
    with pytest.raises(AdapterRateLimitedError) as exc_info:
        asyncio.run(adapter.search("Fort"))
    assert exc_info.value.retry_after_seconds == 2.0


def test_search_results_are_cached(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, [NOMINATIM_SEARCH_ITEM])]))
    _install_fake_client(monkeypatch, fake)

    adapter = NominatimGeocodingAdapter(_settings())

    async def _twice() -> None:
        await adapter.search("Fort Mumbai")
        await adapter.search("Fort Mumbai")  # should hit the cache, not the fake client again

    asyncio.run(_twice())
    assert len(fake.calls) == 1


def test_user_agent_header_is_configured(monkeypatch) -> None:
    fake = FakeAsyncClient(sequence_responder([make_response(200, [NOMINATIM_SEARCH_ITEM])]))
    _install_fake_client(monkeypatch, fake)

    settings = _settings()
    adapter = NominatimGeocodingAdapter(settings)
    asyncio.run(adapter.search("Fort"))

    assert fake.calls[0]["headers"]["User-Agent"] == settings.nominatim_user_agent
    assert "Mozilla" not in settings.nominatim_user_agent  # not a spoofed browser UA


def test_no_autocomplete_route_exists(client) -> None:
    spec = client.get("/openapi.json").json()
    assert not any("autocomplete" in path for path in spec["paths"])
