"""Add the vetted Overture catalog add-on without resetting existing rows.

The committed snapshot contains only non-synthetic, active Overture place
records with per-record license and source provenance.  This importer is
idempotent: it inserts only source IDs that are not already in the catalog.
It never deletes or updates existing catalog, traveler, itinerary, or safety
records.

Usage (from apps/api):
    python scripts/import_overture_catalog_addon.py          # dry run
    python scripts/import_overture_catalog_addon.py --apply   # additive import
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.core.db import async_session_factory, engine  # noqa: E402
from src.models import Experience, ExperienceCategory, Location, Provider  # noqa: E402

API_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = API_ROOT / "data" / "processed" / "overture_catalog_addon.json"
ATTRIBUTION_TEMPLATE = (
    "Place data © {source_name} via the Overture Maps Foundation "
    "(Overture Places, release {version}), licensed {license}."
)


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _load_candidates() -> list[dict[str, Any]]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Overture add-on snapshot must be a JSON array.")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict) or row.get("source_type") != "overture_places":
            raise ValueError("Snapshot contains a non-Overture record.")
        if row.get("source_record_id") in (None, "") or row["source_record_id"] in seen:
            raise ValueError("Snapshot has a missing or duplicate source record ID.")
        if any(not row.get(field) for field in ("source_name", "source_license", "source_version", "source_url")):
            raise ValueError("Snapshot contains a record without complete source provenance.")
        latitude, longitude = row.get("latitude"), row.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError("Snapshot contains a record without coordinates.")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Snapshot contains invalid coordinates.")
        if not row.get("name") or not row.get("category_slug"):
            raise ValueError("Snapshot contains a record without a name or mapped category.")
        seen.add(row["source_record_id"])
        records.append(row)
    return records


def _description(name: str, category_name: str, locality: str | None, city: str) -> tuple[str, str]:
    place = locality or city
    short = f"{category_name} in {place}, {city}." if place != city else f"{category_name} in {city}."
    full = (
        f"{name} is listed under {category_name} in {place}, {city}, sourced from open place data "
        "(Overture Maps Places). LocaLens has not independently verified opening hours, pricing, "
        "or current status for this listing."
    )
    return short, full


async def _existing_source_ids(session: AsyncSession) -> set[str]:
    result = await session.execute(
        select(Experience.source_record_id).where(
            Experience.source_type == "overture_places",
            Experience.source_record_id.is_not(None),
        )
    )
    return {source_id for source_id in result.scalars().all() if source_id}


async def import_catalog(*, apply: bool) -> None:
    candidates = _load_candidates()
    async with async_session_factory() as session:
        async with session.begin():
            existing_ids = await _existing_source_ids(session)
            missing = [row for row in candidates if row["source_record_id"] not in existing_ids]
            categories = (await session.execute(select(ExperienceCategory))).scalars().all()
            categories_by_slug = {category.slug: category for category in categories}
            missing_categories = sorted({row["category_slug"] for row in missing} - categories_by_slug.keys())
            if missing_categories:
                raise ValueError(f"Local category taxonomy is missing: {', '.join(missing_categories)}")

            print(
                f"Snapshot records: {len(candidates)}; already present: {len(candidates) - len(missing)}; "
                f"new records: {len(missing)}."
            )
            if not apply:
                print("Dry run only. Re-run with --apply to add the missing Overture records.")
                return
            if not missing:
                print("Catalog already contains every source record; nothing changed.")
                return

            existing_providers = (
                await session.execute(select(Provider).where(Provider.source_type == "overture_places"))
            ).scalars().all()
            providers_by_name = {
                _normalized_name(provider.business_name): provider for provider in existing_providers
            }
            now = datetime.now(UTC)
            for index, row in enumerate(missing, start=1):
                category = categories_by_slug[row["category_slug"]]
                provider_key = row.get("normalized_name") or _normalized_name(row["name"])
                provider = providers_by_name.get(provider_key)
                source_name = row["source_name"]
                license_value = row["source_license"]
                version = row["source_version"]
                source_url = row["source_url"]
                attribution = ATTRIBUTION_TEMPLATE.format(
                    source_name=source_name,
                    version=version,
                    license=license_value,
                )
                if provider is None:
                    provider = Provider(
                        business_name=row["name"],
                        provider_type="catalog_place",
                        city=row["city"],
                        verification_status="catalog_imported",
                        source_type="overture_places",
                        source_name=source_name,
                        source_record_id=row.get("source_place_record_id"),
                        source_version=version,
                        source_accessed_at=now,
                        source_url=source_url,
                        source_license=license_value,
                        attribution_required=True,
                        attribution_text=attribution,
                        source_confidence=row.get("source_confidence"),
                        is_synthetic=False,
                        is_enriched=False,
                    )
                    session.add(provider)
                    providers_by_name[provider_key] = provider

                location = Location(
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    place_name=row["name"],
                    address=row.get("address"),
                    locality=row.get("locality"),
                    city=row["city"],
                    state=row.get("state"),
                    country=row.get("country"),
                    postal_code=row.get("postal_code"),
                    timezone="Asia/Kolkata",
                    source_type="overture_places",
                    source_name=source_name,
                    source_record_id=row["source_record_id"],
                    source_version=version,
                    source_accessed_at=now,
                    source_url=source_url,
                    source_license=license_value,
                    attribution_required=True,
                    attribution_text=attribution,
                    source_confidence=row.get("source_confidence"),
                    is_synthetic=False,
                    is_enriched=False,
                )
                session.add(location)

                short_description, full_description = _description(
                    row["name"], category.name, row.get("locality"), row["city"]
                )
                price_low = row.get("estimated_price_low")
                price_high = row.get("estimated_price_high")
                has_estimated_price = price_low is not None and price_high is not None
                duration = row.get("estimated_duration_minutes")
                experience = Experience(
                    provider=provider,
                    category=category,
                    location=location,
                    title=row["name"],
                    short_description=short_description,
                    full_description=full_description,
                    currency="INR",
                    minimum_price=price_low,
                    maximum_price=price_high,
                    price_type="range" if has_estimated_price else "unknown",
                    price_source="estimated" if has_estimated_price else "unavailable",
                    is_price_estimated=has_estimated_price,
                    duration_minutes=duration,
                    duration_is_estimated=duration is not None,
                    status="active",
                    verification_status="catalog_imported",
                    suitability=None,
                    tags=[row["category_slug"]],
                    rating=None,
                    rating_source=None,
                    review_count=None,
                    opening_hours_status="unavailable",
                    source_type="overture_places",
                    source_name=source_name,
                    source_record_id=row["source_record_id"],
                    source_version=version,
                    source_accessed_at=now,
                    source_url=source_url,
                    source_license=license_value,
                    attribution_required=True,
                    attribution_text=attribution,
                    source_confidence=row.get("source_confidence"),
                    is_synthetic=False,
                    is_enriched=True,
                )
                session.add(experience)
                if index % 250 == 0:
                    await session.flush()
                    print(f"Prepared {index}/{len(missing)} records.")
            await session.flush()

        print(f"Added {len(missing)} Overture catalog records. Existing rows were preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="commit missing catalog records")
    args = parser.parse_args()
    try:
        asyncio.run(import_catalog(apply=args.apply))
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()
