"""SSE live-itinerary-update delivery (Phase 9).

An in-process pub/sub event bus keyed by itinerary_id — single-process
only (docs/DECISIONS.md: this app runs as a single uvicorn process in
dev, see scripts/dev.ps1/dev.sh; a multi-worker/multi-instance production
deployment would need a shared broker (e.g. Redis pub/sub) instead of
this in-memory dict, which is an explicitly documented limitation, not
solved here — see docs/DECISIONS.md Phase 9 ADR).

Events: connected, context_update, replan_started, replan_completed,
replan_failed, requires_action, booking_status_update, heartbeat. Every
event carries a monotonically increasing id (per itinerary) so a
reconnecting client can resume via the standard SSE Last-Event-ID header
(supported implicitly — a reconnect simply subscribes fresh and receives
new events going forward; this process keeps no event replay buffer,
which is a documented limitation for a hackathon-scope single process).
Never streams raw external API responses or API keys — only normalized
application event payloads.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

_HEARTBEAT_INTERVAL_SECONDS = 15


@dataclass
class _ItineraryBus:
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    event_id_counter: itertools.count = field(default_factory=lambda: itertools.count(1))


_buses: dict[str, _ItineraryBus] = {}
_buses_lock = asyncio.Lock()


async def _get_or_create_bus(itinerary_id: str) -> _ItineraryBus:
    async with _buses_lock:
        bus = _buses.get(itinerary_id)
        if bus is None:
            bus = _ItineraryBus()
            _buses[itinerary_id] = bus
        return bus


def build_sse_event(event_type: str, event_id: int, data: dict[str, object]) -> str:
    payload = json.dumps(data, default=str)
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


async def publish_itinerary_event(itinerary_id: str, event_type: str, data: dict[str, object]) -> None:
    """Publishes a normalized event to every current subscriber of this
    itinerary's SSE stream. Called by ReplanningService/ContextMonitor —
    never receives or forwards raw provider payloads."""
    bus = await _get_or_create_bus(itinerary_id)
    event_id = next(bus.event_id_counter)
    message = build_sse_event(event_type, event_id, data)
    for queue in list(bus.subscribers):
        queue.put_nowait(message)


async def sse_updates_stream(itinerary_id: str) -> AsyncIterator[str]:
    bus = await _get_or_create_bus(itinerary_id)
    queue: asyncio.Queue[str] = asyncio.Queue()
    bus.subscribers.append(queue)

    try:
        first_id = next(bus.event_id_counter)
        yield build_sse_event(
            "connected",
            first_id,
            {"itinerary_id": itinerary_id, "connected_at": datetime.now(UTC).isoformat()},
        )
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL_SECONDS)
                yield message
            except TimeoutError:
                heartbeat_id = next(bus.event_id_counter)
                yield build_sse_event(
                    "heartbeat", heartbeat_id, {"at": datetime.now(UTC).isoformat()}
                )
    finally:
        if queue in bus.subscribers:
            bus.subscribers.remove(queue)


async def publish_collab_event(group_id: str, event_type: str, data: dict[str, object]) -> None:
    """Publish a normalized group event over the existing in-process SSE
    transport. The channel prefix keeps group and itinerary identifiers
    isolated while reusing the project's current realtime mechanism."""
    await publish_itinerary_event(f"collab:{group_id}", f"collab_{event_type}", {"group_id": group_id, **data})


async def sse_collab_updates_stream(group_id: str) -> AsyncIterator[str]:
    """Authenticated routes call this only after verifying group
    membership. Delivery has the same single-process limitation as the
    existing itinerary event bus."""
    channel_id = f"collab:{group_id}"
    bus = await _get_or_create_bus(channel_id)
    queue: asyncio.Queue[str] = asyncio.Queue()
    bus.subscribers.append(queue)
    try:
        first_id = next(bus.event_id_counter)
        yield build_sse_event(
            "connected", first_id, {"group_id": group_id, "connected_at": datetime.now(UTC).isoformat()}
        )
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL_SECONDS)
                yield message
            except TimeoutError:
                heartbeat_id = next(bus.event_id_counter)
                yield build_sse_event("heartbeat", heartbeat_id, {"at": datetime.now(UTC).isoformat()})
    finally:
        if queue in bus.subscribers:
            bus.subscribers.remove(queue)


__all__ = [
    "build_sse_event", "publish_collab_event", "publish_itinerary_event",
    "sse_collab_updates_stream", "sse_updates_stream",
]
