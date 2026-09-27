"""Structured errors for external-service adapters.

Routes/services catch these and translate to an honest, graceful
response (e.g. "travel time unavailable") — never a raw 500, and never
silently fabricated data.
"""

from __future__ import annotations


class AdapterError(Exception):
    """Base class for all adapter failures."""


class AdapterTimeoutError(AdapterError):
    pass


class AdapterRateLimitedError(AdapterError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AdapterUnavailableError(AdapterError):
    """The external service returned an error or malformed response."""


class AdapterNoResultError(AdapterError):
    """The external service responded successfully but found nothing
    (e.g. no route between two points, no geocoding match)."""
