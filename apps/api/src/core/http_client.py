"""Shared async HTTP client foundation for outbound external-service calls.

Every adapter (Nominatim, OSRM, Overpass) goes through this — never a new
`httpx.AsyncClient()` per adapter, per docs/DECISIONS.md ADR-022. One
client per process is reused for connection pooling; explicit timeouts
are always set; a descriptive User-Agent is always sent.
"""

from __future__ import annotations

from functools import lru_cache

import httpx

from src.core.config import get_settings


@lru_cache
def get_http_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.external_http_timeout_seconds),
        headers={"User-Agent": settings.nominatim_user_agent},
        follow_redirects=True,
    )


async def close_http_client() -> None:
    client = get_http_client()
    await client.aclose()
    get_http_client.cache_clear()
