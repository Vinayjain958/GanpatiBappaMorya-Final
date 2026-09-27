"""Resolve real Wikimedia Commons images for existing Experience rows.

Iterates every Experience, skips any that already has a verified
non-synthetic image (Wikimedia or a real provider upload) unless
--refresh is passed, then runs the full matching ladder in
src/services/experience_images.py against the live Wikimedia Commons
API. Never fabricates a match — an experience with no suitable image is
left as NO_SUITABLE_IMAGE and reported honestly in the summary.

Usage (from apps/api):
    python scripts/enrich_experience_images.py [--limit N] [--refresh] [--dry-run]

Flags:
    --limit N     Process at most N experiences.
    --refresh     Re-resolve even experiences that already have a
                  wikimedia_commons/category_fallback image (never
                  touches provider_upload/traveler_upload images
                  regardless of this flag).
    --dry-run     Report classifications without writing anything.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from src.adapters.wikimedia_commons import RealWikimediaCommonsAdapter  # noqa: E402
from src.core.config import get_settings  # noqa: E402
from src.core.db import async_session_factory  # noqa: E402
from src.models.experience import Experience  # noqa: E402
from src.services.experience_images import ImageMatch, resolve_experience_image  # noqa: E402

# Self-imposed bounded concurrency for the Wikimedia API — matches the
# rate-limiter discipline used by scripts/index_embeddings.py, but kept
# low (this is a single external API, not a fan-out of adapters).
_CONCURRENCY = 3

# Classification labels for the summary report (task requirement #17/#36).
PROVIDER_OWNED = "PROVIDER_OWNED_IMAGE"
TRAVELER_OWNED = "TRAVELER_OWNED_IMAGE"
WIKIMEDIA_PLACE_SPECIFIC = "WIKIMEDIA_PLACE_SPECIFIC"
WIKIMEDIA_NEARBY = "WIKIMEDIA_NEARBY"
WIKIMEDIA_SEMANTIC = "WIKIMEDIA_SEMANTIC"
EXISTING_VALID = "EXISTING_VALID_IMAGE"
NO_SUITABLE_IMAGE = "NO_SUITABLE_IMAGE"
FAILED = "FAILED"


def _classify_match(match: ImageMatch) -> str:
    if match.matched_by in ("exact_commons_link", "exact_title", "exact_wikidata"):
        return WIKIMEDIA_PLACE_SPECIFIC
    if match.matched_by in ("nearby_strong_match", "nearby_geographic"):
        return WIKIMEDIA_NEARBY
    return WIKIMEDIA_SEMANTIC


async def _process_one(
    session: AsyncSession,
    experience: Experience,
    adapter: RealWikimediaCommonsAdapter,
    settings,
    *,
    refresh: bool,
    dry_run: bool,
    stats: Counter,
    rows: list[dict],
) -> None:
    # Rule #19 precedence: a real provider-owned upload is never touched.
    if experience.image_source == "provider_upload":
        stats[PROVIDER_OWNED] += 1
        rows.append({"title": experience.title, "result": PROVIDER_OWNED, "detail": experience.image_url})
        return

    # Same precedence for a traveler's own contributed photo — it is
    # stronger evidence of the actual venue than any Wikimedia match.
    if experience.image_source == "traveler_upload":
        stats[TRAVELER_OWNED] += 1
        rows.append({"title": experience.title, "result": TRAVELER_OWNED, "detail": experience.image_url})
        return

    already_enriched = experience.image_source in ("wikimedia_commons", "category_fallback") and experience.image_url
    if already_enriched and not refresh:
        stats[EXISTING_VALID] += 1
        rows.append({"title": experience.title, "result": EXISTING_VALID, "detail": experience.image_url})
        return

    try:
        match = await resolve_experience_image(
            experience_title=experience.title,
            provider_name=experience.provider.business_name if experience.provider else experience.title,
            location_name=experience.location.place_name if experience.location else None,
            category_slug=experience.category.slug if experience.category else "",
            latitude=experience.location.latitude,
            longitude=experience.location.longitude,
            known_commons_file=None,  # Overture Places carries no OSM/Wikimedia linkage today
            adapter=adapter,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001 — one bad record must not crash the run
        stats[FAILED] += 1
        rows.append({"title": experience.title, "result": FAILED, "detail": str(exc)})
        print(f"  FAILED  {experience.id} ({experience.title!r}): {exc}")
        return

    if match is None:
        stats[NO_SUITABLE_IMAGE] += 1
        rows.append({"title": experience.title, "result": NO_SUITABLE_IMAGE, "detail": None})
        return

    classification = _classify_match(match)
    stats[classification] += 1
    rows.append(
        {
            "title": experience.title,
            "result": classification,
            "detail": f"{match.matched_by} score={match.match_score:.1f} {match.image_url}",
        }
    )

    if dry_run:
        return

    experience.image_url = match.image_url
    experience.image_thumbnail_url = match.thumbnail_url
    experience.image_source = match.source
    experience.image_source_url = match.source_url
    experience.image_source_id = match.source_id
    experience.image_license = match.license
    experience.image_license_url = match.license_url
    experience.image_author = match.author
    experience.image_attribution_text = match.attribution_text
    experience.image_is_place_specific = match.is_place_specific
    experience.image_is_synthetic = match.is_synthetic
    experience.image_match_method = match.matched_by
    experience.image_match_score = match.match_score
    experience.image_retrieved_at = match.retrieved_at
    await session.commit()


async def run(*, limit: int | None, refresh: bool, dry_run: bool) -> None:
    settings = get_settings()
    adapter = RealWikimediaCommonsAdapter(settings)

    stats: Counter = Counter()
    rows: list[dict] = []

    async with async_session_factory() as session:
        stmt = select(Experience).options(
            selectinload(Experience.category),
            selectinload(Experience.location),
            selectinload(Experience.provider),
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        experiences = list(result.scalars().unique().all())

        semaphore = asyncio.Semaphore(_CONCURRENCY)

        async def _bounded(experience: Experience) -> None:
            async with semaphore:
                await _process_one(
                    session, experience, adapter, settings, refresh=refresh, dry_run=dry_run, stats=stats, rows=rows
                )

        # Sequential await over bounded tasks — a single AsyncSession is
        # not safe for true concurrent use (same discipline as
        # scripts/index_embeddings.py); the semaphore exists so the
        # pattern generalizes cleanly if this ever moves to per-record
        # sessions, and documents the intended concurrency bound.
        for experience in experiences:
            await _bounded(experience)

    total = len(experiences)
    print(f"\nTOTAL EXPERIENCES: {total}\n")
    print(f"PROVIDER-OWNED IMAGE:        {stats[PROVIDER_OWNED]}")
    print(f"WIKIMEDIA PLACE-SPECIFIC:    {stats[WIKIMEDIA_PLACE_SPECIFIC]}")
    print(f"WIKIMEDIA NEARBY:            {stats[WIKIMEDIA_NEARBY]}")
    print(f"WIKIMEDIA SEMANTIC:          {stats[WIKIMEDIA_SEMANTIC]}")
    print(f"EXISTING VALID (unchanged):  {stats[EXISTING_VALID]}")
    print(f"NO SUITABLE IMAGE:           {stats[NO_SUITABLE_IMAGE]}")
    print(f"FAILED:                      {stats[FAILED]}")

    # Duplicate-image diagnostic (task requirement #28) — flag any single
    # image URL reused across an unexpectedly large number of experiences.
    url_counts = Counter(r["detail"].split()[-1] for r in rows if r["result"] == WIKIMEDIA_SEMANTIC and r["detail"])
    suspicious = {url: count for url, count in url_counts.items() if count > 5}
    if suspicious:
        print("\nSUSPICIOUS HIGH-REUSE SEMANTIC-FALLBACK IMAGES (>5 experiences):")
        for url, count in sorted(suspicious.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>3}x  {url}")

    if dry_run:
        print("\n(dry run — no changes written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Wikimedia Commons images for Experience rows.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(run(limit=args.limit, refresh=args.refresh, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
