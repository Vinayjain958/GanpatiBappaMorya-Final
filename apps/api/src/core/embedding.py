"""FastAPI dependency provider for the embedding adapter (Phase 6).

Mirrors src/core/ai.py's selection rule exactly: real GeminiEmbeddingAdapter
only when GEMINI_ENABLED=true AND GEMINI_API_KEY is set, otherwise
MockEmbeddingAdapter — the app must always start, embeddings degrade
gracefully to the deterministic mock rather than failing startup.
"""

from __future__ import annotations

from functools import lru_cache

from src.adapters.embedding import EmbeddingAdapter, GeminiEmbeddingAdapter, MockEmbeddingAdapter
from src.core.config import get_settings


@lru_cache
def get_embedding_adapter() -> EmbeddingAdapter:
    settings = get_settings()
    if not (settings.gemini_enabled and settings.gemini_api_key):
        return MockEmbeddingAdapter(dimensions=settings.gemini_embedding_dimensions)
    return GeminiEmbeddingAdapter(settings)


__all__ = ["get_embedding_adapter"]
