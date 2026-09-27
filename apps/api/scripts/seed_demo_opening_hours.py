"""Add clearly labeled demo hours and availability to experiences missing them.

This is for exercising Trips schedule checks and open/closed UI. Generated
schedules are illustrative, not venue-confirmed facts. Existing hours and
availability are never changed.

Run from apps/api:
    python scripts/seed_demo_opening_hours.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.db import async_session_factory
from src.models.availability import ExperienceAvailability
from src.models.experience import Experience
from src.models.opening_hour import ExperienceOpeningHour
from src.services.synthetic_experience_enrichment import (
    DEFAULT_GLOBAL_SEED,
    SYNTHETIC_ENRICHMENT_VERSION,
    generate_synthetic_opening_hours,
    get_seeded_rng,
)

_DEFAULT_TIMEZONE = ZoneInfo("Asia/Kolkata")
_DEMO_DAYS_FORWARD = 60


def _demo_availability(
    experience: Experience,
    hours: list[ExperienceOpeningHour],
    *,
    today: date,
) -> list[ExperienceAvailability]:
    timezone_name = experience.location.timezone or "Asia/Kolkata"
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception:
        timezone = _DEFAULT_TIMEZONE

    capacity = max(1, experience.capacity or experience.maximum_group_size or 10)
    by_weekday: dict[int, list[ExperienceOpeningHour]] = {}
    for hour in hours:
        by_weekday.setdefault(hour.day_of_week, []).append(hour)

    slots: list[ExperienceAvailability] = []
    for day_offset in range(_DEMO_DAYS_FORWARD + 1):
        target_day = today + timedelta(days=day_offset)
        for hour in by_weekday.get(target_day.weekday(), []):
            if hour.is_closed or not hour.open_time or not hour.close_time:
                continue
            opens = time.fromisoformat(hour.open_time)
            closes = time.fromisoformat(hour.close_time)
            starts_at = datetime.combine(target_day, opens, tzinfo=timezone)
            ends_day = target_day + timedelta(days=1) if closes <= opens else target_day
            ends_at = datetime.combine(ends_day, closes, tzinfo=timezone)
            slots.append(ExperienceAvailability(
                experience_id=experience.id,
                starts_at=starts_at.astimezone(ZoneInfo("UTC")),
                ends_at=ends_at.astimezone(ZoneInfo("UTC")),
                capacity=capacity,
                available_slots=capacity,
                status="active",
                source_type="demo_schedule",
                is_synthetic=True,
            ))
    return slots


async def seed_demo_hours(session: AsyncSession) -> tuple[int, int, int, int]:
    result = await session.execute(
        select(Experience)
        .options(
            selectinload(Experience.category),
            selectinload(Experience.location),
            selectinload(Experience.opening_hours),
            selectinload(Experience.availability_slots),
        )
        .order_by(Experience.id.asc())
    )
    experiences = list(result.scalars().unique().all())
    added_experiences = 0
    added_windows = 0
    availability_experiences = 0
    availability_slots = 0

    for experience in experiences:
        effective_hours = list(experience.opening_hours)
        if not effective_hours:
            schedules = generate_synthetic_opening_hours(
                experience,
                get_seeded_rng(experience.id, version=SYNTHETIC_ENRICHMENT_VERSION, global_seed=DEFAULT_GLOBAL_SEED),
            )
            effective_hours = [
                ExperienceOpeningHour(
                    experience_id=experience.id,
                    day_of_week=schedule.day_of_week,
                    open_time=schedule.open_time,
                    close_time=schedule.close_time,
                    is_closed=schedule.is_closed,
                    source_type="demo_schedule",
                    is_synthetic=True,
                )
                for schedule in schedules
            ]
            session.add_all(effective_hours)
            experience.opening_hours_status = "synthetic"
            added_experiences += 1
            added_windows += len(effective_hours)

        if not experience.availability_slots:
            demo_slots = _demo_availability(
                experience, effective_hours, today=datetime.now(_DEFAULT_TIMEZONE).date()
            )
            session.add_all(demo_slots)
            availability_experiences += bool(demo_slots)
            availability_slots += len(demo_slots)

    await session.commit()
    return added_experiences, added_windows, availability_experiences, availability_slots


async def main() -> None:
    async with async_session_factory() as session:
        experiences, windows, availability_experiences, availability_slots = await seed_demo_hours(session)
    print("DEMO SCHEDULE — illustrative hours and availability; not venue-confirmed")
    print(f"Experiences enriched: {experiences}")
    print(f"Weekly hours rows added: {windows}")
    print(f"Experiences with demo availability: {availability_experiences}")
    print(f"Daily availability windows added: {availability_slots}")
    print("Existing recorded hours were preserved.")


if __name__ == "__main__":
    asyncio.run(main())
