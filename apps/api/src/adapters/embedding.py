"""EmbeddingAdapter — asymmetric query/document embedding generation (Phase 6).

Deliberately a separate interface from AIAdapter (src/adapters/ai.py):
embeddings are a distinct capability (vector generation, not structured
text generation or Live tokens), and asymmetric retrieval needs an
explicit query-vs-document distinction in the API surface itself, not
just in prompt text (docs/DECISIONS.md ADR-042).

GeminiEmbeddingAdapter uses the official `google-genai` SDK
(`client.aio.models.embed_content`). Error handling mirrors
src/adapters/ai.py's `_translate_sdk_error` — the same typed adapter
error hierarchy (src/adapters/errors.py), so callers already handling
AdapterError from the AI/location adapters get the same treatment here.
Never logs API keys or full traveler query text at more than debug-safe
granularity.

MockEmbeddingAdapter is deterministic (hash/token-feature based, NOT
random) so tests and offline/no-key dev get stable, reproducible vectors
of the configured dimensionality — clearly labelled synthetic, never
mistaken for a real semantic embedding.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from google.genai import errors as genai_errors

from src.adapters.errors import AdapterNoResultError, AdapterRateLimitedError, AdapterUnavailableError
from src.core.config import Settings
from src.core.rate_limit import IntervalRateLimiter


class EmbeddingAdapter(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_document(self, title: str, text: str) -> list[float]: ...

    async def embed_documents(self, documents: list[tuple[str, str]]) -> list[list[float]]: ...


def _translate_sdk_error(exc: Exception) -> Exception:
    if isinstance(exc, genai_errors.ClientError):
        if exc.code == 429:
            return AdapterRateLimitedError(str(exc))
        return AdapterUnavailableError(str(exc))
    if isinstance(exc, (genai_errors.ServerError, TimeoutError, ConnectionError)):
        return AdapterUnavailableError(str(exc))
    return AdapterUnavailableError(str(exc))


def _query_prompt(text: str) -> str:
    return f"task: search result | query: {text}"


def _document_prompt(title: str, text: str) -> str:
    return f"title: {title} | text: {text}"


class MockEmbeddingAdapter:
    """Deterministic, non-ML, hash/token-feature based embedding — used
    for tests/CI/no-key dev. NOT a real semantic embedding; captures only
    coarse token-overlap signal so similarity ordering in tests is
    reproducible without a network dependency."""

    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    def _vector_for(self, prompt_text: str) -> list[float]:
        tokens = re.findall(r"[a-z0-9]+", prompt_text.lower())
        vector = [0.0] * self._dimensions
        if not tokens:
            # Stable non-zero fallback vector for empty input.
            digest = hashlib.sha256(b"__empty__").digest()
            for i in range(self._dimensions):
                vector[i] = (digest[i % len(digest)] / 255.0) - 0.5
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            # Feature-hash the token into a handful of dimensions, each
            # contribution scaled by a deterministic sign derived from the
            # digest — a bounded, cheap bag-of-tokens fingerprint.
            for k in range(8):
                idx = int.from_bytes(digest[k * 2 : k * 2 + 2], "big") % self._dimensions
                sign = 1.0 if digest[(k + 8) % len(digest)] % 2 == 0 else -1.0
                vector[idx] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(_query_prompt(text))

    async def embed_document(self, title: str, text: str) -> list[float]:
        return self._vector_for(_document_prompt(title, text))

    async def embed_documents(self, documents: list[tuple[str, str]]) -> list[list[float]]:
        return [self._vector_for(_document_prompt(title, text)) for title, text in documents]


class GeminiEmbeddingAdapter:
    """Real Gemini embedding adapter — google-genai SDK. NOT VERIFIED
    live (no API key available in this environment); implemented against
    the documented `client.models.embed_content` / `.aio.models` async
    surface and the current `gemini-embedding-2` model name."""

    def __init__(self, settings: Settings) -> None:
        from google import genai  # local import mirrors src/adapters/ai.py's pattern

        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._limiter = IntervalRateLimiter(settings.gemini_min_interval_seconds)
        self._model = settings.gemini_embedding_model
        self._dimensions = settings.gemini_embedding_dimensions

    async def _embed(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        from google.genai import types

        await self._limiter.wait()
        try:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._dimensions,
                ),
            )
        except genai_errors.APIError as exc:
            raise _translate_sdk_error(exc) from exc
        except (TimeoutError, ConnectionError) as exc:
            raise AdapterUnavailableError(str(exc)) from exc

        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            raise AdapterNoResultError("Gemini embedding response contained no vectors.")
        return [list(e.values) for e in embeddings]

    async def embed_query(self, text: str) -> list[float]:
        results = await self._embed([_query_prompt(text)], task_type="RETRIEVAL_QUERY")
        return results[0]

    async def embed_document(self, title: str, text: str) -> list[float]:
        results = await self._embed([_document_prompt(title, text)], task_type="RETRIEVAL_DOCUMENT")
        return results[0]

    async def embed_documents(self, documents: list[tuple[str, str]]) -> list[list[float]]:
        if not documents:
            return []
        prompts = [_document_prompt(title, text) for title, text in documents]
        return await self._embed(prompts, task_type="RETRIEVAL_DOCUMENT")


__all__ = ["EmbeddingAdapter", "GeminiEmbeddingAdapter", "MockEmbeddingAdapter"]
