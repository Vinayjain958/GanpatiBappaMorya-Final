"""In-process TTL cache for external-service responses.

Prototype-grade only: this is a single-process dict, not shared across
multiple server instances/workers (docs/DECISIONS.md ADR-022). It exists
so repeated Nominatim/OSRM/Overpass lookups for the same input (e.g. the
same location search during a demo) don't re-hit the public service and
don't burn the 1 req/sec Nominatim budget. Failures are never cached —
only successful, parsed results.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable


class TTLCache[T]:
    def __init__(self, default_ttl_seconds: float) -> None:
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T, ttl_seconds: float | None = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        self._store[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        self._store.clear()

    async def get_or_set(
        self, key: str, factory: Callable[[], Awaitable[T]], ttl_seconds: float | None = None
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = await factory()
        self.set(key, value, ttl_seconds)
        return value
