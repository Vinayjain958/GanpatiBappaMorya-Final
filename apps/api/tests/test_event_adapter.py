"""TicketmasterEventAdapter unit tests (Phase 9) — fake HTTP client only."""

from __future__ import annotations

import asyncio

import pytest

from src.adapters.errors import AdapterRateLimitedError, AdapterUnavailableError
from src.adapters.events import ExternalEventStatus, SeedEventAdapter, TicketmasterEventAdapter
from src.core.config import Settings
from tests.adapter_fakes import FakeAsyncClient, make_response, sequence_responder

EVENT_PAYLOAD = {
    "_embedded": {
        "events": [
            {
                "id": "evt-1",
                "name": "Mumbai Jazz Night",
                "info": "A live jazz performance.",
                "url": "https://ticketmaster.example/evt-1",
                "dates": {
                    "start": {"dateTime": "2026-10-12T19:00:00Z"},
                    "end": {"dateTime": "2026-10-12T21:00:00Z"},
                    "status": {"code": "onsale"},
                },
                "classifications": [{"segment": {"name": "Music"}}],
                "images": [{"url": "https://img.example/evt-1.jpg"}],
                "_embedded": {
                    "venues": [
                        {
                            "name": "Fort Amphitheatre",
                            "address": {"line1": "1 Fort Road"},
                            "location": {"latitude": "18.9346", "longitude": "72.8356"},
                        }
                    ]
                },
            }
        ]
    }
}

CANCELLED_PAYLOAD = {
    "_embedded": {
        "events": [
            {
                "id": "evt-2",
                "name": "Cancelled Concert",
                "url": "https://ticketmaster.example/evt-2",
                "dates": {
                    "start": {"dateTime": "2026-10-12T19:00:00Z"},
                    "status": {"code": "cancelled"},
                },
            }
        ]
    }
}

RESCHEDULED_PAYLOAD = {
    "_embedded": {
        "events": [
            {
                "id": "evt-3",
                "name": "Rescheduled Show",
                "url": "https://ticketmaster.example/evt-3",
                "dates": {
                    "start": {"dateTime": "2026-11-01T19:00:00Z"},
                    "status": {"code": "rescheduled"},
                },
            }
        ]
    }
}


def _settings(**overrides) -> Settings:
    return Settings(ticketmaster_api_key="test-key", events_min_interval_seconds=0.0, **overrides)


def _patch_client(monkeypatch, client: FakeAsyncClient) -> None:
    monkeypatch.setattr("src.adapters.events.get_http_client", lambda: client)


def test_normalizes_live_event(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, EVENT_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))

    assert len(events) == 1
    event = events[0]
    assert event.name == "Mumbai Jazz Night"
    assert event.status == ExternalEventStatus.SCHEDULED
    assert event.venue_name == "Fort Amphitheatre"
    assert event.latitude == 18.9346
    assert event.is_synthetic is False
    assert event.source == "ticketmaster"


def test_cancelled_status_normalized(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, CANCELLED_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))

    assert events[0].status == ExternalEventStatus.CANCELLED


def test_rescheduled_status_normalized(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, RESCHEDULED_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))

    assert events[0].status == ExternalEventStatus.RESCHEDULED


def test_missing_status_code_is_unknown_never_cancelled(monkeypatch) -> None:
    payload = {
        "_embedded": {
            "events": [
                {"id": "evt-4", "name": "No status event", "url": "https://x", "dates": {}}
            ]
        }
    }
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, payload)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))

    assert events[0].status == ExternalEventStatus.UNKNOWN


def test_malformed_event_record_skipped_not_fabricated(monkeypatch) -> None:
    payload = {"_embedded": {"events": [{"name": "missing id field"}]}}
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, payload)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))

    assert events == []


def test_401_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(401, {})]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))


def test_403_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(403, {})]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))


def test_429_raises_rate_limited(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(429, {}, headers={"Retry-After": "5"})]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    with pytest.raises(AdapterRateLimitedError):
        asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))


def test_5xx_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(500, {})]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))


def test_empty_result_is_valid_not_error(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, {"_embedded": {"events": []}})]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings())

    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))

    assert events == []


def test_cache_hit_skips_second_http_call(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, EVENT_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(_settings(events_cache_ttl_seconds=900))

    async def _twice():
        await adapter.search_events(18.9346, 72.8356, 5000)
        await adapter.search_events(18.9346, 72.8356, 5000)

    asyncio.run(_twice())

    assert len(client.calls) == 1


def test_seed_adapter_returns_empty_never_fabricates() -> None:
    adapter = SeedEventAdapter()
    events = asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))
    assert events == []


def test_missing_api_key_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, EVENT_PAYLOAD)]))
    _patch_client(monkeypatch, client)
    adapter = TicketmasterEventAdapter(Settings(ticketmaster_api_key=""))

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_events(18.9346, 72.8356, 5000))
    assert len(client.calls) == 0
