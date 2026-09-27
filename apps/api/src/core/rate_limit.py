"""Minimal outbound-call rate limiter for external geospatial services.

Serializes and paces calls to a single external service to a configured
minimum interval — e.g. never more than 1 Nominatim request/second from
this process, per Nominatim's usage policy (docs/DECISIONS.md ADR-022).
This is intentionally simple (a lock + last-call timestamp), not a
distributed token bucket — adequate for a single-process prototype.
"""

from __future__ import annotations

import asyncio
import time


class IntervalRateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call_monotonic: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._last_call_monotonic is not None:
                elapsed = now - self._last_call_monotonic
                remaining = self._min_interval - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_call_monotonic = time.monotonic()
