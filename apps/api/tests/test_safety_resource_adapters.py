"""Live/fallback safety-resource lookup tests — Phase 11 bug fix.

Covers the live/fallback test matrix: live success, live zero results,
live failure + auto fallback, explicit fallback mode, explicit live
mode + failure (no silent fallback), distance correctness, and
deterministic distance-based sorting. All HTTP calls are faked — no
real network access (tests/adapter_fakes.py pattern)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from src.core.config import Settings
from src.services.safety.resource_adapters import (
    MapboxSafetyResourceAdapter,
    OSMSafetyResourceAdapter,
    SafetyAdapterTimeoutError,
    SafetyAdapterUnavailableError,
    SeedSafetyResourceAdapter,
)
from src.services.safety.safety_resources import (
    InvalidRadiusError,
    SafetyResourceServiceError,
    get_nearby_safety_resources,
)
from tests.adapter_fakes import FakeAsyncClient, make_response, sequence_responder

# NYC-ish test coordinate.
LAT, LNG = 40.7128, -74.0060

OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": LAT + 0.001,  # ~111m away — nearest
            "lon": LNG,
            "tags": {"name": "Nearby General Hospital", "amenity": "hospital", "phone": "+1-555-0100"},
        },
        {
            "type": "node",
            "id": 2,
            "lat": LAT + 0.01,  # ~1.1km away — farther
            "lon": LNG,
            "tags": {"name": "Far Hospital", "amenity": "hospital"},
        },
        {
            "type": "node",
            "id": 3,
            "lat": LAT + 0.002,
            "lon": LNG,
            "tags": {"name": "Local Police Precinct", "amenity": "police"},
        },
        {
            "type": "way",
            "id": 4,
            "center": {"lat": LAT + 0.003, "lon": LNG},
            "tags": {"name": "Embassy of Testland", "office": "diplomatic", "diplomatic": "embassy"},
        },
        {
            # No coordinates and no center — must be skipped, never crash.
            "type": "relation",
            "id": 5,
            "tags": {"name": "Broken element", "amenity": "hospital"},
        },
    ]
}

EMPTY_OVERPASS_RESPONSE: dict = {"elements": []}


def _settings(**overrides) -> Settings:
    # mapbox_api_key defaults to empty here regardless of what a real
    # .env file has configured — tests that specifically exercise the
    # Mapbox tier pass an explicit mapbox_api_key override.
    defaults = {"safety_resources_min_interval_seconds": 0.0, "mapbox_api_key": ""}
    defaults.update(overrides)
    return Settings(**defaults)


def _install_fake_client(monkeypatch, fake: FakeAsyncClient) -> None:
    monkeypatch.setattr("src.services.safety.resource_adapters.get_http_client", lambda: fake)


# ─── TEST A — LIVE SUCCESS ──────────────────────────────────────────────────


def test_live_success_returns_real_results_marked_non_synthetic(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, None))

    assert len(results) == 4  # the malformed 5th element is skipped
    assert all(r.is_synthetic is False for r in results)
    assert all(r.source == "openstreetmap" for r in results)
    hospital = next(r for r in results if r.name == "Nearby General Hospital")
    assert hospital.phone == "+1-555-0100"


def test_live_success_hospitals_police_consulates_all_present(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, None))

    types = {r.type for r in results}
    assert types == {"hospital", "police", "consulate"}


def test_consulate_normalizes_office_diplomatic_tag(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "consulate"))

    assert len(results) == 1
    assert results[0].name == "Embassy of Testland"
    assert results[0].type == "consulate"


# ─── Distance correctness + deterministic sorting ───────────────────────────


def test_distance_calculated_from_actual_query_coordinates(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "hospital"))

    nearest = next(r for r in results if r.name == "Nearby General Hospital")
    farthest = next(r for r in results if r.name == "Far Hospital")
    # ~111m for 0.001 deg latitude — tolerance generous but catches gross errors.
    assert 0.05 < nearest.distance_km < 0.2
    assert 0.9 < farthest.distance_km < 1.3


def test_results_sorted_by_numeric_distance_not_string(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "hospital"))

    distances = [r.distance_km for r in results]
    assert distances == sorted(distances)


# ─── TEST B — LIVE ZERO RESULTS ─────────────────────────────────────────────


def test_live_zero_results_returns_honest_empty_list(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, EMPTY_OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings())
    )

    assert results == []


# ─── TEST C — LIVE FAILURE + AUTO FALLBACK ──────────────────────────────────


def test_auto_mode_falls_back_to_seed_on_network_error(monkeypatch) -> None:
    def _raise_network_error(**_kwargs):
        raise httpx.ConnectError("connection refused")

    client = FakeAsyncClient(responder=_raise_network_error)
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="auto"))
    )

    assert len(results) > 0
    assert all(r.is_synthetic is True for r in results)
    assert all(r.source == "seed_fallback" for r in results)


def test_auto_mode_falls_back_on_timeout(monkeypatch) -> None:
    client = FakeAsyncClient(responder=lambda **_kwargs: (_ for _ in ()).throw(httpx.TimeoutException("timed out")))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="auto"))
    )

    assert all(r.is_synthetic is True for r in results)


def test_auto_mode_falls_back_on_malformed_response(monkeypatch) -> None:
    # One malformed response per URL tried: primary + all configured mirrors.
    client = FakeAsyncClient(responder=lambda **_kwargs: make_response(200, None))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="auto"))
    )

    assert all(r.is_synthetic is True for r in results)


def test_auto_mode_does_not_fallback_merely_because_live_is_empty(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, EMPTY_OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="auto"))
    )

    assert results == []  # not seed data


def test_mirror_used_when_primary_load_sheds(monkeypatch) -> None:
    calls = {"count": 0}

    def _responder(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return make_response(504)  # primary load-shedding
        return make_response(200, OVERPASS_RESPONSE)  # mirror succeeds

    client = FakeAsyncClient(responder=_responder)
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "hospital"))

    assert calls["count"] == 2
    assert len(results) > 0
    assert all(r.is_synthetic is False for r in results)


def test_all_mirrors_failing_raises_and_auto_falls_back(monkeypatch) -> None:
    client = FakeAsyncClient(responder=lambda **_kwargs: make_response(504))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="auto"))
    )

    assert all(r.is_synthetic is True for r in results)


# ─── Mapbox second-tier live provider ───────────────────────────────────────

MAPBOX_RESPONSE = {
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [LNG, LAT + 0.001]},
            "properties": {
                "name": "Mapbox General Hospital",
                "mapbox_id": "abc123",
                "full_address": "1 Health St, Testville",
                "metadata": {"phone": "+1-555-0199"},
                "distance": 111.0,
            },
        }
    ]
}


def test_mapbox_used_when_overpass_and_mirrors_all_fail(monkeypatch) -> None:
    def _responder(**kwargs):
        if kwargs.get("method") == "GET":
            return make_response(200, MAPBOX_RESPONSE)
        return make_response(504)  # Overpass + all mirrors load-shedding

    client = FakeAsyncClient(responder=_responder)
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(
            LAT, LNG, 5.0, "hospital",
            settings=_settings(safety_resources_mode="auto", mapbox_api_key="test-key"),
        )
    )

    assert len(results) > 0
    assert all(r.source == "mapbox" for r in results)
    assert all(r.is_synthetic is False for r in results)
    assert results[0].name == "Mapbox General Hospital"
    assert results[0].phone == "+1-555-0199"


def test_mapbox_skipped_without_api_key_falls_to_seed(monkeypatch) -> None:
    # No mapbox_api_key configured — Mapbox tier must not even attempt a
    # request; auto mode should go straight to seed data. Explicit empty
    # override: real deployments/dev .env files may have a key set, so
    # this must not silently pick one up from the environment.
    client = FakeAsyncClient(responder=lambda **_kwargs: make_response(504))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(
            LAT, LNG, 5.0, None,
            settings=_settings(safety_resources_mode="auto", mapbox_api_key=""),
        )
    )

    assert all(r.is_synthetic is True for r in results)
    assert all(kwargs.get("method") != "GET" for kwargs in client.calls)  # no Mapbox GET attempted


def test_live_mode_tries_mapbox_before_raising(monkeypatch) -> None:
    def _responder(**kwargs):
        if kwargs.get("method") == "GET":
            return make_response(429)  # Mapbox also fails
        return make_response(504)  # Overpass + mirrors fail

    client = FakeAsyncClient(responder=_responder)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(SafetyResourceServiceError):
        asyncio.run(
            get_nearby_safety_resources(
                LAT, LNG, 5.0, None,
                settings=_settings(safety_resources_mode="live", mapbox_api_key="test-key"),
            )
        )


def test_mapbox_adapter_filters_results_outside_radius(monkeypatch) -> None:
    far_response = {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [LNG, LAT]},
                "properties": {
                    "name": "Too Far Hospital",
                    "mapbox_id": "far1",
                    "distance": 50_000.0,  # 50km, outside a 5km radius
                },
            }
        ]
    }
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, far_response)]))
    _install_fake_client(monkeypatch, client)
    adapter = MapboxSafetyResourceAdapter(_settings(mapbox_api_key="test-key"))

    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "hospital"))

    assert results == []


def test_mapbox_adapter_raises_when_key_missing() -> None:
    adapter = MapboxSafetyResourceAdapter(_settings(mapbox_api_key=""))

    with pytest.raises(SafetyAdapterUnavailableError):
        asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "hospital"))


# ─── TEST D — EXPLICIT FALLBACK MODE ────────────────────────────────────────


def test_fallback_mode_always_uses_seed_data(monkeypatch) -> None:
    # Even with a working live provider, fallback mode must not call it.
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)

    results = asyncio.run(
        get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="fallback"))
    )

    assert all(r.is_synthetic is True for r in results)
    assert client.calls == []  # live adapter never invoked


# ─── TEST E — EXPLICIT LIVE MODE + FAILURE (no silent fallback) ────────────


def test_live_mode_raises_service_error_never_silently_falls_back(monkeypatch) -> None:
    def _raise_network_error(**_kwargs):
        raise httpx.ConnectError("connection refused")

    client = FakeAsyncClient(responder=_raise_network_error)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(SafetyResourceServiceError):
        asyncio.run(
            get_nearby_safety_resources(LAT, LNG, 5.0, None, settings=_settings(safety_resources_mode="live"))
        )


# ─── Provenance on seed adapter ─────────────────────────────────────────────


def test_seed_adapter_never_claims_live_provenance() -> None:
    adapter = SeedSafetyResourceAdapter()
    results = asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, None))

    assert len(results) > 0
    assert all(r.is_synthetic is True for r in results)
    assert all(r.source != "openstreetmap" for r in results)


# ─── Validation ──────────────────────────────────────────────────────────────


def test_radius_below_minimum_rejected() -> None:
    with pytest.raises(InvalidRadiusError):
        asyncio.run(get_nearby_safety_resources(LAT, LNG, 0.01, None, settings=_settings()))


def test_radius_above_maximum_rejected() -> None:
    with pytest.raises(InvalidRadiusError):
        asyncio.run(get_nearby_safety_resources(LAT, LNG, 999, None, settings=_settings()))


def test_unknown_category_rejected(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, OVERPASS_RESPONSE)]))
    _install_fake_client(monkeypatch, client)
    adapter = OSMSafetyResourceAdapter(_settings())

    with pytest.raises(ValueError):
        asyncio.run(adapter.get_nearby_resources(LAT, LNG, 5.0, "not-a-real-category"))


# ─── Query construction ─────────────────────────────────────────────────────


def test_query_construction_is_deterministic() -> None:
    from src.services.safety.resource_adapters import _build_overpass_query

    query = _build_overpass_query(LAT, LNG, 5000, ["hospital"])
    assert f'node(around:5000,{LAT},{LNG})["amenity"="hospital"];' in query
    assert query == _build_overpass_query(LAT, LNG, 5000, ["hospital"])
