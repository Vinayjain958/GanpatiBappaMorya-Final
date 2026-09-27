"""Populate the database from:
  1. data/processed/overture_experiences.json (produced by ingest_overture.py)
  2. the synthetic provider/experience generator (scripts/synthetic_data.py)

Usage:
    cd apps/api
    python scripts/seed.py

This script reseeds only the two catalog lineages it owns —
source_type="overture_places" and source_type="synthetic" — so it is
always safe to re-run against the same database. It never touches:
  - User/Traveler accounts
  - Provider/Experience/Location rows with source_type in
    ("registered", "provider_submitted") — i.e. real accounts created
    through the app (Phase 3). Categories are shared by both lineages,
    so they are upserted by slug (stable IDs) rather than wiped, which
    would otherwise orphan provider-created experiences' category_id.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from scripts.synthetic_data import generate_synthetic_dataset  # noqa: E402
from src.core.category_map import CATEGORIES  # noqa: E402
from src.core.db import async_session_factory, engine  # noqa: E402
from src.models import (  # noqa: E402
    Experience,
    ExperienceAvailability,
    ExperienceCategory,
    ExperienceOpeningHour,
    Location,
    Provider,
)

API_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = API_ROOT / "data" / "processed" / "overture_experiences.json"

SYNTHETIC_EXPERIENCE_TARGET = 65
SYNTHETIC_PROVIDER_TARGET = 50

OVERTURE_ATTRIBUTION_TEMPLATE = (
    "Place data © {source_name} via the Overture Maps Foundation "
    "(Overture Places, release {version}), licensed {license}."
)

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


_RESEEDABLE_SOURCE_TYPES = ("overture_places", "synthetic")


async def reset_tables(session: AsyncSession) -> None:
    """Deletes only rows this script owns (Overture-derived + synthetic
    demo). Real accounts (source_type="registered"/"provider_submitted",
    created via /api/v1/auth/register and /api/v1/experiences) are never
    touched. SQLite does not reliably enforce ON DELETE CASCADE, so
    dependents are deleted explicitly rather than relied on implicitly.
    """
    experience_ids_query = select(Experience.id).where(Experience.source_type.in_(_RESEEDABLE_SOURCE_TYPES))
    experience_ids = (await session.execute(experience_ids_query)).scalars().all()

    if experience_ids:
        await session.execute(
            delete(ExperienceOpeningHour).where(ExperienceOpeningHour.experience_id.in_(experience_ids))
        )
        await session.execute(
            delete(ExperienceAvailability).where(ExperienceAvailability.experience_id.in_(experience_ids))
        )
        await session.execute(delete(Experience).where(Experience.id.in_(experience_ids)))

    await session.execute(delete(Location).where(Location.source_type.in_(_RESEEDABLE_SOURCE_TYPES)))
    await session.execute(delete(Provider).where(Provider.source_type.in_(_RESEEDABLE_SOURCE_TYPES)))
    await session.commit()


async def seed_categories(session: AsyncSession) -> dict[str, ExperienceCategory]:
    """Upsert-by-slug rather than delete-and-recreate: category IDs must
    stay stable across reseeds since provider-created experiences
    (source_type="provider_submitted") reference them by ID."""
    existing_rows = (await session.execute(select(ExperienceCategory))).scalars().all()
    existing_by_slug = {row.slug: row for row in existing_rows}

    categories: dict[str, ExperienceCategory] = {}
    for definition in CATEGORIES:
        category = existing_by_slug.get(definition.slug)
        if category is None:
            category = ExperienceCategory(slug=definition.slug)
            session.add(category)
        category.name = definition.name
        category.description = definition.description
        category.icon = definition.icon
        category.sort_order = definition.sort_order
        categories[definition.slug] = category
    await session.flush()
    return categories


def _overture_description(name: str, category_name: str, locality: str) -> tuple[str, str]:
    short = f"{category_name} in {locality}, Mumbai."
    full = (
        f"{name} is listed under {category_name} in {locality}, Mumbai, sourced from open place "
        f"data (Overture Maps Places). LocaLens has not yet independently verified opening hours, "
        f"pricing, or current status for this listing."
    )
    return short, full


async def seed_overture_experiences(
    session: AsyncSession, categories: dict[str, ExperienceCategory]
) -> tuple[int, int]:
    if not PROCESSED_PATH.exists():
        print(f"No processed Overture data found at {PROCESSED_PATH} — skipping source-derived seed.")
        return 0, 0

    candidates = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"))
    providers_by_key: dict[str, Provider] = {}
    experience_count = 0

    from src.core.category_map import CATEGORIES as CATEGORY_DEFS

    category_names = {c.slug: c.name for c in CATEGORY_DEFS}

    for candidate in candidates:
        category = categories.get(candidate["category_slug"])
        if category is None:
            continue

        provider_key = candidate["normalized_name"]
        provider = providers_by_key.get(provider_key)
        if provider is None:
            license_value = candidate.get("source_license") or "unknown"
            provider = Provider(
                business_name=candidate["name"],
                provider_type="catalog_place",
                city=candidate["city"],
                verification_status="catalog_imported",
                source_type="overture_places",
                source_name=candidate.get("source_name"),
                source_record_id=candidate.get("source_place_record_id"),
                source_version=candidate["source_version"],
                source_accessed_at=datetime.now(UTC),
                source_url=candidate["source_url"],
                source_license=license_value,
                attribution_required=True,
                attribution_text=OVERTURE_ATTRIBUTION_TEMPLATE.format(
                    source_name=candidate.get("source_name") or "Overture contributors",
                    version=candidate["source_version"],
                    license=license_value,
                ),
                source_confidence=candidate.get("source_confidence"),
                is_synthetic=False,
                is_enriched=False,
            )
            session.add(provider)
            providers_by_key[provider_key] = provider

        location = Location(
            latitude=candidate["latitude"],
            longitude=candidate["longitude"],
            place_name=candidate["name"],
            address=candidate.get("address"),
            locality=candidate["locality"],
            city=candidate["city"],
            state=candidate.get("state"),
            country=candidate.get("country", "India"),
            postal_code=candidate.get("postal_code"),
            source_type="overture_places",
            source_name=candidate.get("source_name"),
            source_record_id=candidate["source_record_id"],
            source_version=candidate["source_version"],
            source_accessed_at=datetime.now(UTC),
            source_url=candidate["source_url"],
            source_license=candidate.get("source_license") or "unknown",
            attribution_required=True,
            source_confidence=candidate.get("source_confidence"),
            is_synthetic=False,
            is_enriched=False,
        )
        session.add(location)

        short_desc, full_desc = _overture_description(
            candidate["name"], category_names.get(candidate["category_slug"], "experience"), candidate["locality"]
        )

        experience = Experience(
            provider=provider,
            category=category,
            location=location,
            title=candidate["name"],
            short_description=short_desc,
            full_description=full_desc,
            currency="INR",
            minimum_price=candidate["estimated_price_low"],
            maximum_price=candidate["estimated_price_high"],
            price_type="range",
            price_source="estimated",
            is_price_estimated=True,
            duration_minutes=candidate["estimated_duration_minutes"],
            duration_is_estimated=True,
            status="active",
            verification_status="catalog_imported",
            wheelchair_accessible=None,
            step_free=None,
            suitability=["solo", "couple", "friends"],
            tags=[candidate["category_slug"], candidate["locality"].lower()],
            rating=None,
            review_count=None,
            opening_hours_status="unavailable",
            source_type="overture_places",
            source_name=candidate.get("source_name"),
            source_record_id=candidate["source_record_id"],
            source_version=candidate["source_version"],
            source_accessed_at=datetime.now(UTC),
            source_url=candidate["source_url"],
            source_license=candidate.get("source_license") or "unknown",
            attribution_required=True,
            attribution_text=OVERTURE_ATTRIBUTION_TEMPLATE.format(
                source_name=candidate.get("source_name") or "Overture contributors",
                version=candidate["source_version"],
                license=candidate.get("source_license") or "unknown",
            ),
            source_confidence=candidate.get("source_confidence"),
            is_synthetic=False,
            is_enriched=True,
        )
        session.add(experience)
        experience_count += 1

    await session.flush()
    return len(providers_by_key), experience_count


async def seed_synthetic(session: AsyncSession, categories: dict[str, ExperienceCategory]) -> tuple[int, int]:
    synthetic_providers, synthetic_experiences = generate_synthetic_dataset(
        target_experience_count=SYNTHETIC_EXPERIENCE_TARGET,
        provider_count=SYNTHETIC_PROVIDER_TARGET,
    )

    provider_rows: dict[str, Provider] = {}
    for sp in synthetic_providers:
        provider = Provider(
            business_name=sp.business_name,
            provider_type=sp.provider_type,
            city=sp.city,
            verification_status="unverified",
            source_type="synthetic",
            is_synthetic=True,
            is_enriched=False,
        )
        session.add(provider)
        provider_rows[sp.key] = provider
    await session.flush()

    for index, se in enumerate(synthetic_experiences):
        provider = provider_rows[se.provider_key]
        category = categories[se.category_slug]

        location = Location(
            latitude=se.latitude,
            longitude=se.longitude,
            place_name=se.title,
            locality=se.locality,
            city="Mumbai",
            state="MH",
            country="India",
            source_type="synthetic",
            is_synthetic=True,
            is_enriched=False,
        )
        session.add(location)

        short_desc = f"A synthetic demo {category.name.lower()} experience in {se.locality}, Mumbai."
        full_desc = (
            f"{se.title} is a LocaLens demo experience created for prototype purposes. It is not a "
            f"real bookable offering. Duration, pricing, and availability shown are illustrative estimates."
        )

        experience = Experience(
            provider=provider,
            category=category,
            location=location,
            title=se.title,
            short_description=short_desc,
            full_description=full_desc,
            currency="INR",
            minimum_price=se.price_low,
            maximum_price=se.price_high,
            price_type="range",
            price_source="estimated",
            is_price_estimated=True,
            duration_minutes=se.duration_minutes,
            duration_is_estimated=True,
            minimum_group_size=1,
            maximum_group_size=8,
            capacity=8,
            status="active",
            verification_status="curated",
            wheelchair_accessible=None,
            step_free=None,
            suitability=se.suitability,
            tags=[se.category_slug, se.locality.lower(), "demo"],
            rating=None,
            review_count=None,
            opening_hours_status="structured",
            source_type="synthetic",
            source_record_id=f"synthetic-{index}",
            source_version="localens-demo-v1",
            source_accessed_at=datetime.now(UTC),
            attribution_required=False,
            is_synthetic=True,
            is_enriched=True,
        )
        session.add(experience)
        await session.flush()

        for day_of_week, open_time, close_time in se.opening_hours:
            session.add(
                ExperienceOpeningHour(
                    experience_id=experience.id,
                    day_of_week=day_of_week,
                    open_time=open_time,
                    close_time=close_time,
                    is_closed=False,
                )
            )

    await session.flush()
    return len(provider_rows), len(synthetic_experiences)


async def main() -> None:
    async with async_session_factory() as session:
        print("Resetting catalog tables ...")
        await reset_tables(session)

        print("Seeding categories ...")
        categories = await seed_categories(session)

        print("Seeding Overture-derived experiences ...")
        overture_providers, overture_experiences = await seed_overture_experiences(session, categories)

        print("Seeding synthetic demo experiences ...")
        synthetic_providers, synthetic_experiences = await seed_synthetic(session, categories)

        await session.commit()

        location_count = (await session.execute(select(Location.id))).scalars().all()

        print("\n--- Seed summary ---")
        print(f"Categories:              {len(categories)}")
        print(f"Overture-derived providers: {overture_providers}")
        print(f"Overture-derived experiences: {overture_experiences}")
        print(f"Synthetic providers:     {synthetic_providers}")
        print(f"Synthetic experiences:   {synthetic_experiences}")
        print(f"Total providers:         {overture_providers + synthetic_providers}")
        print(f"Total experiences:       {overture_experiences + synthetic_experiences}")
        print(f"Total locations:         {len(location_count)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
