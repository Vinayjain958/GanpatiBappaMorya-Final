"""SemanticRetrievalService (Phase 6).

query -> embed -> retrieve candidates -> similarity -> SAFE deterministic
pre-filters (active status, category, city/locality) -> candidate pool.

Never makes a feasibility decision (budget/hours/capacity/etc. stay
exclusively FeasibilityService's job — docs/DECISIONS.md ADR-042/ADR-043).

Three retrieval modes, always honestly reported via `retrieval_mode`:
  - "pgvector_semantic"     — PostgreSQL, native pgvector ORDER BY (NOT
                               VERIFIED live — no Postgres instance here).
  - "sqlite_python_semantic" — SQLite, bounded candidate load + Python
                               cosine similarity (the verified default).
  - "keyword_fallback"      — embeddings unavailable/disabled; reuses the
                               existing Phase 4 ExperienceDiscoveryService
                               keyword search rather than a second engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.embedding import EmbeddingAdapter
from src.core.config import Settings
from src.core.vector_math import cosine_similarity
from src.models.experience import Experience
from src.repositories.embedding_repository import EmbeddingRepository
from src.repositories.experience_repository import ExperienceFilters, ExperienceRepository
from src.services.discovery import DiscoveryQuery, ExperienceDiscoveryService
from src.services.embedding_text import build_query_text

RetrievalMode = str  # "pgvector_semantic" | "sqlite_python_semantic" | "keyword_fallback"


@dataclass
class SemanticCandidate:
    experience: Experience
    similarity: float | None  # None under keyword_fallback


@dataclass
class SemanticRetrievalResult:
    items: list[SemanticCandidate]
    retrieval_mode: RetrievalMode
    candidate_count: int


class SemanticRetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        embedding_adapter: EmbeddingAdapter | None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._embedding_adapter = embedding_adapter
        self._experience_repo = ExperienceRepository(session)
        self._embedding_repo = EmbeddingRepository(session)

    async def retrieve(
        self,
        *,
        raw_query: str | None,
        interests: list[str] | None = None,
        category_slug: str | None = None,
        city: str | None = None,
        locality: str | None = None,
        location_text: str | None = None,
        pool_size: int | None = None,
    ) -> SemanticRetrievalResult:
        pool_size = min(
            pool_size or self._settings.semantic_candidate_pool_size,
            self._settings.semantic_max_candidate_pool_size,
        )

        if not self._settings.semantic_search_enabled or self._embedding_adapter is None:
            return await self._keyword_fallback(raw_query, category_slug, city, locality, pool_size)

        query_text = build_query_text(
            raw_query=raw_query, interests=interests, category=category_slug, location_text=location_text
        )
        if not query_text.strip():
            return await self._keyword_fallback(raw_query, category_slug, city, locality, pool_size)

        try:
            query_vector = await self._embedding_adapter.embed_query(query_text)
        except Exception:
            # Embedding generation failed (adapter error) -> degrade to the
            # keyword path rather than failing the whole search.
            return await self._keyword_fallback(raw_query, category_slug, city, locality, pool_size)

        dialect = self._session.bind.dialect.name if self._session.bind is not None else "sqlite"
        if dialect == "postgresql":
            return await self._pgvector_search(query_vector, category_slug, pool_size)
        return await self._sqlite_python_search(query_vector, category_slug, city, locality, pool_size)

    async def _keyword_fallback(
        self,
        raw_query: str | None,
        category_slug: str | None,
        city: str | None,
        locality: str | None,
        pool_size: int,
    ) -> SemanticRetrievalResult:
        discovery = ExperienceDiscoveryService(self._experience_repo, self._settings)
        result = await discovery.search(
            DiscoveryQuery(
                q=raw_query, category_slug=category_slug, city=city, locality=locality,
                status="active", limit=pool_size,
            )
        )
        items = [SemanticCandidate(experience=i.experience, similarity=None) for i in result.items]
        return SemanticRetrievalResult(items=items, retrieval_mode="keyword_fallback", candidate_count=len(items))

    async def _pgvector_search(
        self, query_vector: list[float], category_slug: str | None, pool_size: int
    ) -> SemanticRetrievalResult:
        """NOT VERIFIED live — no PostgreSQL instance available."""
        pairs = await self._embedding_repo.search_similar_pgvector(
            query_vector, limit=pool_size, category_slug=category_slug
        )
        by_id = {exp_id: sim for exp_id, sim in pairs}
        candidates: list[SemanticCandidate] = []
        for exp_id, similarity in pairs:
            experience = await self._experience_repo.get_by_id(exp_id)
            if experience is not None and experience.status == "active":
                candidates.append(SemanticCandidate(experience=experience, similarity=similarity))
        return SemanticRetrievalResult(
            items=candidates, retrieval_mode="pgvector_semantic", candidate_count=len(by_id)
        )

    async def _sqlite_python_search(
        self,
        query_vector: list[float],
        category_slug: str | None,
        city: str | None,
        locality: str | None,
        pool_size: int,
    ) -> SemanticRetrievalResult:
        filters = ExperienceFilters(
            category_slug=category_slug, city=city, locality=locality, status="active"
        )
        candidates = await self._experience_repo.search(filters, cap=self._settings.discovery_candidate_cap)

        scored: list[SemanticCandidate] = []
        for experience in candidates:
            embedding_row = await self._embedding_repo.get_by_experience_id(experience.id)
            if embedding_row is None:
                continue
            similarity = cosine_similarity(query_vector, embedding_row.embedding)
            scored.append(SemanticCandidate(experience=experience, similarity=similarity))

        scored.sort(key=lambda c: c.similarity or 0.0, reverse=True)
        page = scored[:pool_size]
        return SemanticRetrievalResult(
            items=page, retrieval_mode="sqlite_python_semantic", candidate_count=len(scored)
        )


__all__ = ["SemanticCandidate", "SemanticRetrievalResult", "SemanticRetrievalService"]
