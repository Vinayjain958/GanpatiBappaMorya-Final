"""experience embeddings

Revision ID: 6762a731d1f1
Revises: ec67b7587043
Create Date: 2026-09-23 00:00:00.000000

Phase 6 semantic embedding storage. Branches per-dialect (docs/DECISIONS.md
ADR-042):
  - PostgreSQL: `CREATE EXTENSION IF NOT EXISTS vector`, a real pgvector
    VECTOR(N) column (`embedding_vector`), and an HNSW cosine index. NOT
    VERIFIED live — no PostgreSQL instance is available in this
    environment; this path is implemented against the documented pgvector
    SQL syntax but has only been read-reviewed, not executed.
  - SQLite: no vector DDL at all — only the portable JSON `embedding`
    column (declared on the ORM model, created by the dialect-agnostic
    `op.create_table` below) is used, and similarity is computed in
    Python (see src/services/semantic_retrieval.py).

The `embedding` JSON column and its owning table are created identically
on both dialects; only the extra pgvector column/index are Postgres-only.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6762a731d1f1'
down_revision: str | Sequence[str] | None = 'ec67b7587043'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        'experience_embeddings',
        sa.Column('experience_id', sa.String(length=36), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('embedding_model', sa.String(length=80), nullable=False),
        sa.Column('embedding_dimensions', sa.Integer(), nullable=False),
        sa.Column('source_content_hash', sa.String(length=64), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False
        ),
        sa.ForeignKeyConstraint(['experience_id'], ['experiences.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experience_id', name='uq_experience_embeddings_experience_id'),
    )
    op.create_index(
        op.f('ix_experience_embeddings_experience_id'), 'experience_embeddings', ['experience_id'], unique=True
    )

    if dialect == 'postgresql':
        # NOT VERIFIED live — no PostgreSQL instance available in this
        # environment. Written against documented pgvector SQL syntax.
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
        op.execute(
            'ALTER TABLE experience_embeddings '
            'ADD COLUMN embedding_vector vector(1536)'
        )
        op.execute(
            'CREATE INDEX ix_experience_embeddings_vector_hnsw '
            'ON experience_embeddings USING hnsw (embedding_vector vector_cosine_ops)'
        )
    # SQLite (and any other non-Postgres dialect): no vector DDL — the
    # portable JSON `embedding` column above is the only storage.


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_experience_embeddings_vector_hnsw')
        op.execute('ALTER TABLE experience_embeddings DROP COLUMN IF EXISTS embedding_vector')

    op.drop_index(op.f('ix_experience_embeddings_experience_id'), table_name='experience_embeddings')
    op.drop_table('experience_embeddings')
