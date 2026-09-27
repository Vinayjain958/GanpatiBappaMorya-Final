"""Backfill ExperienceAvailability rows from existing opening hours (dev/demo data).

Phase 6's FeasibilityService correctly treats availability as UNKNOWN
(never assumed bookable) whenever a traveler supplies a date/time window
and the experience has zero ExperienceAvailability rows on record. The
seeded catalog never had any such rows, so the itinerary composer could
never produce a plan against it — not a bug, just an incomplete demo
dataset. This script derives a concrete bookable slot for each active
experience's opening-hours window, for a configurable number of upcoming
days, so composing an itinerary actually has real data to work with.

This is generated demo/dev data, not real provider-supplied availability
— never claim otherwise to a traveler-facing surface.

Idempotent: skips (experience_id, starts_at) pairs that already exist.

Usage (from apps/api):
    python scripts/seed_availability.py [--days N] [--limit N] [--dry-run]

Flags:
    --days N     Generate slots for the next N days (default 14).
    --limit N    Process at most N experiences.
    --dry-run    Report what would be written without writing anything.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from src.core.config import get_settings  # noqa: E402
from src.core.db import get_session  # noqa: E402
from src.models.availability import ExperienceAvailability  # noqa: E402
from src.models.experience import Experience  # noqa: E402

_DEFAULT_TZ = "Asia/Kolkata"
_DEFAULT_CAPACITY = 8


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ExperienceAvailability from opening hours.")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    written = 0
    skipped_existing = 0
    skipped_no_hours = 0
    processed = 0

    async for session in get_session():
        stmt = (
            select(Experience)
            .where(Experience.status == "active")
            .options(
                selectinload(Experience.opening_hours),
                selectinload(Experience.availability_slots),
                selectinload(Experience.location),
            )
        )
        if args.limit:
            stmt = stmt.limit(args.limit)

        experiences = (await session.execute(stmt)).scalars().all()

        for experience in experiences:
            processed += 1
            hours_by_day: dict[int, list[tuple[time, time]]] = {}
            for oh in experience.opening_hours:
                if oh.is_closed or not oh.open_time or not oh.close_time:
                    continue
                hours_by_day.setdefault(oh.day_of_week, []).append(
                    (_parse_hhmm(oh.open_time), _parse_hhmm(oh.close_time))
                )

            if not hours_by_day:
                skipped_no_hours += 1
                continue

            tzname = (experience.location.timezone if experience.location else None) or _DEFAULT_TZ
            try:
                tz = ZoneInfo(tzname)
            except Exception:
                tz = ZoneInfo(_DEFAULT_TZ)

            # SQLite drops tzinfo on round-trip even for a DateTime(timezone=True)
            # column, so existing rows come back naive while freshly-built
            # `starts_at` values below are tz-aware — compare on the naive
            # form (both are wall-clock-equivalent since we always write in
            # the same tz) rather than risk a silent always-false set lookup.
            existing_starts = {
                slot.starts_at.replace(tzinfo=None) if slot.starts_at.tzinfo else slot.starts_at
                for slot in experience.availability_slots
            }
            capacity = experience.maximum_group_size or _DEFAULT_CAPACITY

            today = date.today()
            for offset in range(args.days):
                day = today + timedelta(days=offset)
                day_of_week = day.weekday()  # 0=Monday, matches ExperienceOpeningHour convention
                for open_t, close_t in hours_by_day.get(day_of_week, []):
                    local_start = datetime.combine(day, open_t, tzinfo=tz)
                    local_end = datetime.combine(day, close_t, tzinfo=tz)
                    if local_end <= local_start:
                        # Overnight window (close < open) — not handled by
                        # this simple demo-data generator; skip rather than
                        # guess at a wraparound slot.
                        continue
                    # Convert to UTC before stripping tzinfo: SQLite drops
                    # tzinfo on write, and FeasibilityService._as_aware
                    # treats a naive stored value as UTC per the model's
                    # documented convention — storing local-wall-clock
                    # numbers as if they were UTC would silently shift
                    # every comparison by the timezone offset.
                    starts_at = local_start.astimezone(UTC)
                    ends_at = local_end.astimezone(UTC)
                    if starts_at.replace(tzinfo=None) in existing_starts:
                        skipped_existing += 1
                        continue

                    written += 1
                    if not args.dry_run:
                        session.add(
                            ExperienceAvailability(
                                experience_id=experience.id,
                                starts_at=starts_at,
                                ends_at=ends_at,
                                capacity=capacity,
                                available_slots=capacity,
                                status="active",
                            )
                        )

        if not args.dry_run:
            await session.commit()
        break

    prefix = "[dry-run] would write" if args.dry_run else "written"
    print(
        f"Processed {processed} active experience(s): {prefix}={written} "
        f"skipped_existing={skipped_existing} skipped_no_opening_hours={skipped_no_hours}"
    )
    if settings.app_env == "production":
        print("WARNING: this generates synthetic demo availability — do not run in production.")


if __name__ == "__main__":
    asyncio.run(main())
