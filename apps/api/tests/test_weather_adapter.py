"""OpenWeatherAdapter unit tests (Phase 9) — fake HTTP client only, no
live network calls, following tests/adapter_fakes.py's established
pattern (see test_geocoding_adapter.py/test_routing_adapter.py)."""

from __future__ import annotations

import asyncio

import pytest

from src.adapters.errors import AdapterRateLimitedError, AdapterUnavailableError
from src.adapters.weather import MockWeatherAdapter, OpenWeatherAdapter, WeatherSource
from src.core.config import Settings
from tests.adapter_fakes import FakeAsyncClient, make_response, sequence_responder

CURRENT_PAYLOAD = {
    "coord": {"lon": 72.83, "lat": 18.93},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
    "main": {"temp": 30.5, "feels_like": 33.0, "humidity": 55},
    "wind": {"speed": 3.1},
    "visibility": 10000,
    "dt": 1700000000,
}

SEVERE_PAYLOAD = {
    "coord": {"lon": 72.83, "lat": 18.93},
    "weather": [{"id": 202, "main": "Thunderstorm", "description": "thunderstorm with heavy rain"}],
    "main": {"temp": 24.0, "feels_like": 25.0, "humidity": 90},
    "wind": {"speed": 15.0},
    "rain": {"1h": 5.2},
    "dt": 1700000000,
}


def _settings(**overrides) -> Settings:
    return Settings(openweather_api_key="test-key", weather_min_interval_seconds=0.0, **overrides)


def _patch_client(monkeypatch, client: FakeAsyncClient) -> None:
    monkeypatch.setattr("src.adapters.weather.get_http_client", lambda: client)


def test_get_current_normalizes_live_response(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, CURRENT_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    context = asyncio.run(adapter.get_current(18.93, 72.83))

    assert context.source == WeatherSource.LIVE
    assert context.temperature_c == 30.5
    assert context.feels_like_c == 33.0
    assert context.condition == "Clear"
    assert context.weather_code == 800
    assert context.severe_alert is False
    assert context.visibility_km == 10.0


def test_severe_weather_code_flags_severe_alert(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, SEVERE_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    context = asyncio.run(adapter.get_current(18.93, 72.83))

    assert context.severe_alert is True
    assert context.precipitation_amount == 5.2


def test_malformed_json_raises_unavailable(monkeypatch) -> None:
    bad_response = make_response(200, None)  # empty body -> invalid JSON
    client = FakeAsyncClient(responder=sequence_responder([bad_response]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.get_current(18.93, 72.83))


def test_401_raises_unavailable_never_fabricates(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(401, {"message": "Invalid API key"})]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.get_current(18.93, 72.83))


def test_403_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(403, {})]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.get_current(18.93, 72.83))


def test_429_raises_rate_limited(monkeypatch) -> None:
    client = FakeAsyncClient(
        responder=sequence_responder([make_response(429, {}, headers={"Retry-After": "2"})])
    )
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    with pytest.raises(AdapterRateLimitedError) as exc_info:
        asyncio.run(adapter.get_current(18.93, 72.83))
    assert exc_info.value.retry_after_seconds == 2.0


def test_5xx_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(503, {})]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.get_current(18.93, 72.83))


def test_cache_hit_skips_second_http_call(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, CURRENT_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings(weather_cache_ttl_seconds=900))

    async def _twice():
        first = await adapter.get_current(18.93, 72.83)
        second = await adapter.get_current(18.93, 72.83)
        return first, second

    first, second = asyncio.run(_twice())

    assert len(client.calls) == 1  # only one real HTTP call
    assert first.source == WeatherSource.LIVE
    assert second.source == WeatherSource.CACHED


def test_missing_api_key_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, CURRENT_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(Settings(openweather_api_key=""))

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.get_current(18.93, 72.83))
    assert len(client.calls) == 0  # never even attempted the HTTP call


def test_mock_adapter_never_labelled_live() -> None:
    adapter = MockWeatherAdapter()

    async def _run():
        context = await adapter.get_current(18.93, 72.83)
        forecast = await adapter.get_forecast(18.93, 72.83)
        return context, forecast

    context, forecast = asyncio.run(_run())
    assert context.source == WeatherSource.MOCK
    assert all(c.source == WeatherSource.MOCK for c in forecast)


def test_get_forecast_normalizes_list(monkeypatch) -> None:
    forecast_payload = {
        "list": [
            {
                "dt": 1700000000,
                "main": {"temp": 28.0, "feels_like": 30.0, "humidity": 70},
                "wind": {"speed": 5.0},
                "weather": [{"id": 500, "main": "Rain"}],
                "pop": 0.8,
                "rain": {"3h": 3.5},
            }
        ]
    }
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, forecast_payload)]))
    _patch_client(monkeypatch, client)
    adapter = OpenWeatherAdapter(_settings())

    forecast = asyncio.run(adapter.get_forecast(18.93, 72.83))

    assert len(forecast) == 1
    assert forecast[0].precipitation_probability == 80.0
    assert forecast[0].precipitation_amount == 3.5
    assert forecast[0].condition == "Rain"
