from __future__ import annotations

import asyncio

from sqlalchemy import select, text

from src.models import Experience, ExperienceCategory, Location, Provider


def test_engine_and_tables_created(test_engine) -> None:
    async def _check() -> list[str]:
        async with test_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            return [row[0] for row in result.fetchall()]

    tables = asyncio.run(_check())
    expected_tables = [
        "users", "travelers", "providers", "experience_categories",
        "locations", "experiences", "experience_opening_hours",
    ]
    for expected in expected_tables:
        assert expected in tables


def test_session_and_relationships_work(session_factory, seeded_ids) -> None:
    async def _check() -> None:
        async with session_factory() as session:
            result = await session.execute(
                select(Experience).where(Experience.id == seeded_ids["experience_id"])
            )
            experience = result.scalar_one()
            # Relationship access triggers lazy/async load via awaitable attrs.
            provider = await session.get(Provider, experience.provider_id)
            category = await session.get(ExperienceCategory, experience.category_id)
            location = await session.get(Location, experience.location_id)

            assert provider is not None and provider.business_name == "Test Provider"
            assert category is not None and category.slug == "food-drink"
            assert location is not None and location.city == "Mumbai"

    asyncio.run(_check())
