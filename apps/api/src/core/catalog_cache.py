"""Short-lived cache for public, non-personal catalog responses.

Discover lists and category chips are identical for every visitor and change
only when a provider edits the catalog, so they are cached in-process for a
couple of minutes. Every provider-side catalog write calls
`invalidate_catalog_cache()`, so a provider's own change shows up
immediately on this instance. Never cache per-user data here.
"""

from __future__ import annotations

from typing import Any

from starlette.datastructures import QueryParams

from src.core.cache import TTLCache

CATALOG_CACHE_TTL_SECONDS = 120

catalog_cache: TTLCache[Any] = TTLCache(CATALOG_CACHE_TTL_SECONDS, max_entries=500)


def catalog_cache_key(name: str, params: QueryParams) -> str:
    return f"{name}?{sorted(params.multi_items())}"


def invalidate_catalog_cache() -> None:
    catalog_cache.clear()
