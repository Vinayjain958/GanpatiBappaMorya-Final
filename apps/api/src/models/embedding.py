"""ExperienceEmbedding — one semantic embedding vector per experience (Phase 6).

Storage is dialect-portable at the SQLAlchemy model level: the `embedding`
column is declared as JSON, which both SQLite and PostgreSQL support
natively. On PostgreSQL, the Alembic migration additionally creates a
real `pgvector` VECTOR(N) column plus an HNSW cosine index
(see alembic/versions/*_experience_embeddings.py) — the JSON column
still exists for portability/debugging, but SemanticRetrievalService's
Postgres path queries the vector column directly via raw SQL, not this
ORM column (docs/DECISIONS.md ADR-042).

`source_content_hash` lets the indexing script skip unchanged experiences
(same hash + model + dimensions -> no re-embed needed) instead of
re-embedding the whole catalog on every run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience


class ExperienceEmbedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experience_embeddings"

    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # Portable JSON float-list representation (used directly on SQLite;
    # kept in sync alongside the real pgvector column on PostgreSQL).
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    experience: Mapped[Experience] = relationship(back_populates="embedding")


__all__ = ["ExperienceEmbedding"]
