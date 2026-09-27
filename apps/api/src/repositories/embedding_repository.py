"""ExperienceEmbedding repository — dialect-aware read path (Phase 6).

`upsert` and `get_by_experience_id` are dialect-portable (plain ORM/JSON
column). `search_similar_pgvector` is PostgreSQL-only (raw SQL against the
pgvector column added by the Phase 6 migration) and is never called on a
SQLite engine — SemanticRetrievalService picks the code path based on
`session.bind.dialect.name` (see src/services/semantic_retrieval.py).
NOT VERIFIED live — no PostgreSQL instance available in this environment.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.embedding import ExperienceEmbedding


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_experience_id(self, experience_id: str) -> ExperienceEmbedding | None:
        result = await self._session.execute(
            select(ExperienceEmbedding).where(ExperienceEmbedding.experience_id == experience_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int) -> list[ExperienceEmbedding]:
        result = await self._session.execute(select(ExperienceEmbedding).limit(limit))
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        experience_id: str,
        embedding: list[float],
        embedding_model: str,
        embedding_dimensions: int,
        source_content_hash: str,
    ) -> ExperienceEmbedding:
        existing = await self.get_by_experience_id(experience_id)
        if existing is not None:
            existing.embedding = embedding
            existing.embedding_model = embedding_model
            existing.embedding_dimensions = embedding_dimensions
            existing.source_content_hash = source_content_hash
            self._session.add(existing)
            return existing

        row = ExperienceEmbedding(
            experience_id=experience_id,
            embedding=embedding,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            source_content_hash=source_content_hash,
        )
        self._session.add(row)
        return row

    async def delete_by_experience_id(self, experience_id: str) -> None:
        await self._session.execute(
            delete(ExperienceEmbedding).where(ExperienceEmbedding.experience_id == experience_id)
        )

    async def search_similar_pgvector(
        self, query_vector: list[float], *, limit: int, category_slug: str | None = None
    ) -> list[tuple[str, float]]:
        """PostgreSQL-only native pgvector cosine ORDER BY, using the HNSW
        index created by the Phase 6 migration. NOT VERIFIED live.
        Returns (experience_id, similarity) pairs, database-side —
        never loads the whole table into Python."""
        from sqlalchemy import text as sql_text

        vector_literal = "[" + ",".join(repr(float(v)) for v in query_vector) + "]"
        category_clause = ""
        params: dict[str, object] = {"vector": vector_literal, "limit": limit}
        if category_slug:
            category_clause = (
                "JOIN experiences e ON e.id = ee.experience_id "
                "JOIN experience_categories c ON c.id = e.category_id AND c.slug = :category_slug"
            )
            params["category_slug"] = category_slug

        query = sql_text(
            f"""
            SELECT ee.experience_id, 1 - (ee.embedding_vector <=> :vector) AS similarity
            FROM experience_embeddings ee
            {category_clause}
            ORDER BY ee.embedding_vector <=> :vector
            LIMIT :limit
            """
        )
        result = await self._session.execute(query, params)
        return [(row[0], float(row[1])) for row in result.fetchall()]


__all__ = ["EmbeddingRepository"]
