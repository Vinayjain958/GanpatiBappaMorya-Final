from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed import reset_tables, seed_categories  # noqa: E402
from src.core.category_map import CATEGORIES  # noqa: E402
from src.models import Experience, ExperienceCategory, Location, Provider  # noqa: E402


def test_reset_tables_preserves_registered_provider_data(session_factory) -> None:
    """The Phase 3 auth/provider-CRUD flow creates rows with
    source_type in ("registered", "provider_submitted"). Re-running the
    Overture/synthetic seed script must never delete them — see
    scripts/seed.py reset_tables()."""

    async def _run() -> None:
        async with session_factory() as session:
            category = ExperienceCategory(
                slug=CATEGORIES[0].slug, name=CATEGORIES[0].name, sort_order=CATEGORIES[0].sort_order
            )
            session.add(category)
            await session.flush()

            registered_provider = Provider(
                business_name="Real Registered Business",
                verification_status="unverified",
                source_type="registered",
                is_synthetic=False,
            )
            session.add(registered_provider)

            catalog_provider = Provider(
                business_name="Catalog Imported Business",
                verification_status="catalog_imported",
                source_type="overture_places",
                is_synthetic=False,
            )
            session.add(catalog_provider)
            await session.flush()

            location = Location(
                latitude=1.0, longitude=1.0, city="Mumbai",
                source_type="provider_submitted", is_synthetic=False,
            )
            session.add(location)
            await session.flush()

            registered_experience = Experience(
                provider_id=registered_provider.id,
                category_id=category.id,
                location_id=location.id,
                title="Real provider-created experience",
                short_description="Should survive reseeding.",
                full_description="Should survive reseeding, at length.",
                status="active",
                verification_status="unverified",
                opening_hours_status="unavailable",
                source_type="provider_submitted",
                is_synthetic=False,
            )
            session.add(registered_experience)
            await session.commit()

            registered_provider_id = registered_provider.id
            catalog_provider_id = catalog_provider.id
            registered_experience_id = registered_experience.id

        async with session_factory() as session:
            await reset_tables(session)
            await seed_categories(session)
            await session.commit()

        from sqlalchemy import select

        async with session_factory() as session:
            surviving_provider = await session.get(Provider, registered_provider_id)
            deleted_catalog_provider = await session.get(Provider, catalog_provider_id)
            surviving_experience = await session.get(Experience, registered_experience_id)
            categories = (await session.execute(select(ExperienceCategory))).scalars().all()

            assert surviving_provider is not None
            assert surviving_provider.business_name == "Real Registered Business"
            assert deleted_catalog_provider is None
            assert surviving_experience is not None
            assert len(categories) == len(CATEGORIES)

    asyncio.run(_run())
