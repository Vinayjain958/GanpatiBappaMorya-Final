"""Minimal per-user inbound rate limiter for public-write endpoints.

`core/rate_limit.py::IntervalRateLimiter` paces this process's own
*outbound* calls to a single external service (Nominatim/OSRM/etc.) — a
different shape of problem to limiting how often one authenticated user
may call one of our own endpoints. This is a small in-memory sliding
window, single-process, matching the "adequate for a single-process
prototype" scope the rest of this codebase's rate limiting already
accepts (no Redis/external rate-limit service).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_seconds: float = 3600.0) -> None:
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        calls = self._calls[key]
        cutoff = now - self._window_seconds
        while calls and calls[0] < cutoff:
            calls.popleft()
        return calls

    def is_limited(self, key: str) -> bool:
        """True when `key` has already used its quota for this window.
        Does not count as a call — pair with record() once the action
        actually succeeds, so failed attempts never consume quota."""
        return len(self._prune(key, time.monotonic())) >= self._max_calls

    def record(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now).append(now)

    def allow(self, key: str) -> bool:
        """Check and record in one step."""
        if self.is_limited(key):
            return False
        self.record(key)
        return True
