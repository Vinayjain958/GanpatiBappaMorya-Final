"""Regression coverage for ADR-060's synthetic-enrichment exclusion.

`scripts/enrich_experience_metadata.py::run_enrichment`'s experience-
selection query must never pick up a traveler_submission experience —
see the comment at that query.
"""

from __future__ import annotations

import asyncio

from scripts.enrich_experience_metadata import run_enrichment
from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.location import Location
from src.models.provider import Provider


def _seed_two_experiences(session_factory) -> dict[str, str]:
    async def _seed() -> dict[str, str]:
        async with session_factory() as session:
            category = ExperienceCategory(slug="enrich-cat", name="Enrich Category", sort_order=1)
            session.add(category)
            await session.flush()

            location = Location(
                latitude=18.93, longitude=72.83, city="Mumbai",
                source_type="overture_places", is_synthetic=False,
            )
            provider = Provider(
                business_name="Enrichable Co", verification_status="catalog_imported",
                source_type="overture_places", is_synthetic=False,
            )
            session.add_all([location, provider])
            await session.flush()

            enrichable = Experience(
                provider=provider, category=category, location=location,
                title="Enrichable Experience", short_description="Can be enriched.",
                full_description="This experience should be picked up by enrichment.",
                status="active", verification_status="catalog_imported",
                opening_hours_status="unavailable",
                source_type="overture_places", source_record_id="enrich-rec-1",
                is_synthetic=False, is_enriched=False,
            )
            session.add(enrichable)
            await session.flush()

            traveler_location = Location(
                latitude=18.94, longitude=72.84, city="Mumbai",
                source_type="traveler_submission", is_synthetic=False,
            )
            community_provider = Provider(
                id="00000000-0000-0000-0000-000000000001",
                business_name="LocaLens Community", provider_type="community",
                verification_status="unverified", source_type="system",
                is_synthetic=False, is_enriched=False,
            )
            session.add_all([traveler_location, community_provider])
            await session.flush()

            traveler_experience = Experience(
                provider=community_provider, category=category, location=traveler_location,
                title="Traveler Submitted Experience", short_description="Must not be enriched.",
                full_description="This experience must be excluded from synthetic enrichment.",
                status="active", verification_status="unverified",
                opening_hours_status="unavailable",
                source_type="traveler_submission", source_name="LocaLens community contribution",
                is_synthetic=False, is_enriched=False,
            )
            session.add(traveler_experience)
            await session.commit()

            return {
                "enrichable_id": enrichable.id,
                "traveler_id": traveler_experience.id,
            }

    return asyncio.run(_seed())


def test_traveler_submission_excluded_from_enrichment_selection(session_factory) -> None:
    _seed_two_experiences(session_factory)

    async def _run():
        async with session_factory() as session:
            report = await run_enrichment(
                session, dry_run=True, regenerate_synthetic=False,
                global_seed=42, version="test-v1",
            )
            return report

    report = asyncio.run(_run())

    # Only the non-traveler_submission experience is inspected.
    assert report.experiences_inspected == 1
