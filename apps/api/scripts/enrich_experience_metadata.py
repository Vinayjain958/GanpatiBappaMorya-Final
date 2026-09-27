"""CLI Script: enrich_experience_metadata.py

Enriches the LocaLens Experience catalog with realistic, reproducible synthetic:
  1. Ratings & Reviews
  2. Opening Hours
  3. Bookable Availability Slots

Usage:
  python scripts/enrich_experience_metadata.py --dry-run
  python scripts/enrich_experience_metadata.py --apply
  python scripts/enrich_experience_metadata.py --apply --regenerate-synthetic
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.db import async_session_factory
from src.models.availability import ExperienceAvailability
from src.models.experience import Experience
from src.models.opening_hour import ExperienceOpeningHour
from src.models.review import ExperienceReview
from src.services.synthetic_experience_enrichment import (
    DEFAULT_GLOBAL_SEED,
    SYNTHETIC_ENRICHMENT_VERSION,
    EnrichmentReport,
    generate_synthetic_availability_slots,
    generate_synthetic_opening_hours,
    generate_synthetic_reviews,
    get_seeded_rng,
)


async def run_enrichment(
    session: AsyncSession,
    *,
    dry_run: bool,
    regenerate_synthetic: bool,
    global_seed: int,
    version: str,
) -> EnrichmentReport:
    report = EnrichmentReport()

    # If regenerate_synthetic requested, purge ONLY synthetic_enrichment records
    if regenerate_synthetic and not dry_run:
        await session.execute(
            delete(ExperienceReview).where(
                ExperienceReview.is_synthetic == True,
                ExperienceReview.source_type == "synthetic_enrichment",
            )
        )
        await session.execute(
            delete(ExperienceOpeningHour).where(
                ExperienceOpeningHour.is_synthetic == True,
                ExperienceOpeningHour.source_type == "synthetic_enrichment",
            )
        )
        await session.execute(
            delete(ExperienceAvailability).where(
                ExperienceAvailability.is_synthetic == True,
                ExperienceAvailability.source_type == "synthetic_enrichment",
            )
        )
        await session.flush()

    # Load all active experiences with relationships. Traveler-contributed
    # places (source_type="traveler_submission") are deliberately excluded:
    # they must never receive a fabricated rating/review/hours just because
    # they exist — they start with zero reviews and only gain real ones.
    query = (
        select(Experience)
        .where(
            Experience.status == "active",
            Experience.source_type != "traveler_submission",
        )
        .options(
            selectinload(Experience.category),
            selectinload(Experience.location),
            selectinload(Experience.provider),
            selectinload(Experience.opening_hours),
            selectinload(Experience.availability_slots),
            selectinload(Experience.reviews),
        )
        .order_by(Experience.created_at.asc(), Experience.id.asc())
    )
    result = await session.execute(query)
    experiences = list(result.scalars().all())
    report.experiences_inspected = len(experiences)

    total_rating_sum = 0
    total_rating_count = 0

    for exp in experiences:
        rng = get_seeded_rng(exp.id, version=version, global_seed=global_seed)

        # ─── 1. Opening Hours ────────────────────────────────────────────────
        existing_hours = list(exp.opening_hours)
        if existing_hours:
            for h in existing_hours:
                if getattr(h, "is_synthetic", False) or getattr(h, "source_type", "") == "synthetic":
                    report.existing_synthetic_hours_preserved += 1
                else:
                    report.existing_authoritative_hours_preserved += 1
            effective_hours = existing_hours
        else:
            # Generate synthetic opening hours
            generated_schedules = generate_synthetic_opening_hours(exp, rng)
            new_hours: list[ExperienceOpeningHour] = []
            for sched in generated_schedules:
                hour_row = ExperienceOpeningHour(
                    experience_id=exp.id,
                    day_of_week=sched.day_of_week,
                    open_time=sched.open_time,
                    close_time=sched.close_time,
                    is_closed=sched.is_closed,
                    source_type="synthetic_enrichment",
                    is_synthetic=True,
                )
                new_hours.append(hour_row)
                report.synthetic_hours_added += 1

            if not dry_run:
                session.add_all(new_hours)
                exp.opening_hours_status = "synthetic"
            effective_hours = new_hours

        # ─── 2. Availability Slots ──────────────────────────────────────────
        existing_avail = list(exp.availability_slots)
        if existing_avail:
            for a in existing_avail:
                if getattr(a, "is_synthetic", False) or getattr(a, "source_type", "") == "synthetic":
                    report.existing_synthetic_avail_preserved += 1
                else:
                    report.existing_authoritative_avail_preserved += 1
        else:
            # Generate valid future slots within opening hours
            new_slots = generate_synthetic_availability_slots(exp, effective_hours, rng)
            report.synthetic_avail_slots_added += len(new_slots)
            if not dry_run:
                session.add_all(new_slots)

        # ─── 3. Ratings & Reviews ───────────────────────────────────────────
        existing_reviews = list(exp.reviews)
        if existing_reviews:
            report.experiences_with_existing_reviews += 1
            for r in existing_reviews:
                report.rating_distribution[r.rating_value] += 1
                total_rating_sum += r.rating_value
                total_rating_count += 1
        else:
            new_reviews = generate_synthetic_reviews(exp, rng, version=version)
            report.experiences_enriched_with_reviews += 1
            report.total_synthetic_reviews_added += len(new_reviews)

            exp_rating_sum = sum(r.rating_value for r in new_reviews)
            exp_review_count = len(new_reviews)
            exp_avg = round(exp_rating_sum / exp_review_count, 1)

            for r in new_reviews:
                report.rating_distribution[r.rating_value] += 1
                total_rating_sum += r.rating_value
                total_rating_count += 1

            if not dry_run:
                session.add_all(new_reviews)
                exp.rating = exp_avg
                exp.review_count = exp_review_count
                exp.rating_source = "synthetic_enrichment"

    if total_rating_count > 0:
        report.average_synthetic_rating = round(total_rating_sum / total_rating_count, 2)
        report.total_reviews_in_db = total_rating_count

    if not dry_run:
        await session.commit()

    return report


def print_report(report: EnrichmentReport, dry_run: bool) -> None:
    mode = "DRY-RUN SIMULATION (No database changes written)" if dry_run else "APPLIED SUCCESSFULLY"
    print("\n" + "=" * 65)
    print(f"EXPERIENCE DATA ENRICHMENT REPORT [{mode}]")
    print("=" * 65)
    print(f"Experiences inspected:                  {report.experiences_inspected}")
    print(f"Experiences with existing reviews:      {report.experiences_with_existing_reviews}")
    print(f"Experiences enriched with reviews:      {report.experiences_enriched_with_reviews}")
    print(f"Total synthetic reviews added:          {report.total_synthetic_reviews_added}")
    print(f"Total reviews in catalog:               {report.total_reviews_in_db}")
    print(f"Average synthetic rating:               {report.average_synthetic_rating:.2f} stars")
    print("Rating Distribution:")
    for star in (5, 4, 3, 2, 1):
        count = report.rating_distribution.get(star, 0)
        pct = (count / report.total_reviews_in_db * 100) if report.total_reviews_in_db else 0
        print(f"  {star}-star: {count:5d} ({pct:5.1f}%)")
    print("-" * 65)
    print(f"Existing authoritative hours preserved: {report.existing_authoritative_hours_preserved}")
    print(f"Existing synthetic hours preserved:     {report.existing_synthetic_hours_preserved}")
    print(f"Synthetic hours rows added:             {report.synthetic_hours_added}")
    print(f"Experiences missing hours:              {report.experiences_missing_hours_after}")
    print("-" * 65)
    print(f"Existing authoritative avail preserved: {report.existing_authoritative_avail_preserved}")
    print(f"Existing synthetic avail preserved:     {report.existing_synthetic_avail_preserved}")
    print(f"Synthetic availability slots added:     {report.synthetic_avail_slots_added}")
    print(f"Experiences without availability:       {report.experiences_without_avail_after}")
    print("=" * 65 + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich experiences with synthetic ratings, reviews, hours & slots")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Simulate enrichment without modifying DB")
    group.add_argument("--apply", action="store_true", help="Apply enrichment changes to database")
    parser.add_argument("--regenerate-synthetic", action="store_true", help="Purge only synthetic_enrichment rows first")
    parser.add_argument("--global-seed", type=int, default=DEFAULT_GLOBAL_SEED, help="Global seed for reproducibility")
    parser.add_argument("--version", type=str, default=SYNTHETIC_ENRICHMENT_VERSION, help="Generation version")

    args = parser.parse_args()

    async with async_session_factory() as session:
        report = await run_enrichment(
            session,
            dry_run=args.dry_run,
            regenerate_synthetic=args.regenerate_synthetic,
            global_seed=args.global_seed,
            version=args.version,
        )
        print_report(report, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
