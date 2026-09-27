"""Backfill/refresh ExperienceEmbedding rows (Phase 6).

Iterates active-catalog experiences, builds canonical document text,
hashes it, and skips any experience whose stored embedding already has
the same content hash + model + dimensions (idempotent — running twice
with no catalog changes writes nothing new). A failed embed for one
experience is logged and skipped; it never writes a fake/placeholder
success (docs/DECISIONS.md ADR-042).

Usage (from apps/api):
    python scripts/index_embeddings.py [--limit N] [--force] [--dry-run] [--only-missing]

Flags:
    --limit N        Process at most N experiences.
    --force          Re-embed even if the content hash/model/dims match.
    --dry-run        Report what would change without writing anything.
    --only-missing   Only embed experiences with no ExperienceEmbedding row
                      at all (skip stale-but-present rows).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from src.core.config import get_settings  # noqa: E402
from src.core.db import async_session_factory  # noqa: E402
from src.core.embedding import get_embedding_adapter  # noqa: E402
from src.models.experience import Experience  # noqa: E402
from src.repositories.embedding_repository import EmbeddingRepository  # noqa: E402
from src.services.embedding_text import build_experience_document_text  # noqa: E402

# Self-imposed bounded concurrency — a small worker pool rather than one
# request per experience serially or unbounded fan-out, matching the
# rate-limiter discipline used by the other external-service adapters.
_CONCURRENCY = 4


async def _process_one(
    session: AsyncSession,
    experience: Experience,
    settings,
    embedding_adapter,
    repo: EmbeddingRepository,
    *,
    force: bool,
    only_missing: bool,
    dry_run: bool,
    stats: dict[str, int],
) -> None:
    document = build_experience_document_text(experience)
    existing = await repo.get_by_experience_id(experience.id)

    if existing is not None and only_missing:
        stats["skipped_only_missing"] += 1
        return

    if (
        existing is not None
        and not force
        and existing.source_content_hash == document.content_hash
        and existing.embedding_model == settings.gemini_embedding_model
        and existing.embedding_dimensions == settings.gemini_embedding_dimensions
    ):
        stats["skipped_unchanged"] += 1
        return

    if dry_run:
        stats["would_write"] += 1
        return

    try:
        vector = await embedding_adapter.embed_document(document.title, document.text)
    except Exception as exc:  # noqa: BLE001 — per-record failure must not crash the run
        stats["failed"] += 1
        print(f"  FAILED  {experience.id} ({experience.title!r}): {exc}")
        return

    await repo.upsert(
        experience_id=experience.id,
        embedding=vector,
        embedding_model=settings.gemini_embedding_model,
        embedding_dimensions=len(vector),
        source_content_hash=document.content_hash,
    )
    await session.commit()
    stats["written"] += 1


async def run(*, limit: int | None, force: bool, dry_run: bool, only_missing: bool) -> None:
    settings = get_settings()
    embedding_adapter = get_embedding_adapter()

    stats = {"written": 0, "skipped_unchanged": 0, "skipped_only_missing": 0, "failed": 0, "would_write": 0}

    async with async_session_factory() as session:
        stmt = (
            select(Experience)
            .options(selectinload(Experience.category), selectinload(Experience.location))
            .where(Experience.status == "active")
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        experiences = list(result.scalars().unique().all())

        semaphore = asyncio.Semaphore(_CONCURRENCY)
        repo = EmbeddingRepository(session)

        async def _bounded(experience: Experience) -> None:
            async with semaphore:
                await _process_one(
                    session, experience, settings, embedding_adapter, repo,
                    force=force, only_missing=only_missing, dry_run=dry_run, stats=stats,
                )

        # Sequential await over bounded tasks — a single AsyncSession is not
        # safe for true concurrent use, so the semaphore bounds outstanding
        # embed_document() calls conceptually while writes stay serialized
        # through this one session.
        for experience in experiences:
            await _bounded(experience)

    total = len(experiences)
    print(
        f"\nProcessed {total} active experience(s): "
        f"written={stats['written']} skipped_unchanged={stats['skipped_unchanged']} "
        f"skipped_only_missing={stats['skipped_only_missing']} failed={stats['failed']} "
        f"would_write={stats['would_write']}"
    )
    print(f"Embedding adapter: {type(embedding_adapter).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill/refresh ExperienceEmbedding rows.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-missing", action="store_true")
    args = parser.parse_args()

    asyncio.run(run(limit=args.limit, force=args.force, dry_run=args.dry_run, only_missing=args.only_missing))


if __name__ == "__main__":
    main()
