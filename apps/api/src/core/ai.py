"""FastAPI dependency provider for the AI adapter.

Selects the real GeminiAIAdapter unless `GEMINI_ENABLED=false` or
`GEMINI_API_KEY` is unset, in which case MockAIAdapter is used instead —
mirrors src/core/location.py's fallback pattern exactly. A per-process
singleton so the adapter's rate limiter persists across requests.
"""

from __future__ import annotations

from functools import lru_cache

from src.adapters.ai import AIAdapter, GeminiAIAdapter, MockAIAdapter
from src.core.config import get_settings
from src.services.ai_tools import (
    CHECK_FEASIBILITY_DECLARATION,
    COMPOSE_EXPERIENCE_DECLARATION,
    REPLAN_EXPERIENCE_DECLARATION,
    SEARCH_EXPERIENCES_DECLARATION,
    SIMULATE_WHAT_IF_DECLARATION,
)


@lru_cache
def get_ai_adapter() -> AIAdapter:
    settings = get_settings()
    if not (settings.gemini_enabled and settings.gemini_api_key):
        return MockAIAdapter()
    return GeminiAIAdapter(
        settings,
        [
            SEARCH_EXPERIENCES_DECLARATION,
            CHECK_FEASIBILITY_DECLARATION,
            COMPOSE_EXPERIENCE_DECLARATION,
            REPLAN_EXPERIENCE_DECLARATION,
            SIMULATE_WHAT_IF_DECLARATION,
        ],
    )
