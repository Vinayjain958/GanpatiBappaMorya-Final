"""Idempotency + precedence tests for scripts/enrich_experience_images.py's
per-record logic — a fake adapter stands in for Wikimedia (no network),
following tests/test_experience_images_matching.py's _FakeAdapter pattern."""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.enrich_experience_images import (  # noqa: E402
    EXISTING_VALID,
    PROVIDER_OWNED,
    WIKIMEDIA_PLACE_SPECIFIC,
    _process_one,
)
from src.adapters.wikimedia_commons import WikimediaImage  # noqa: E402
from src.core.category_map import CATEGORIES  # noqa: E402
from src.core.config import Settings  # noqa: E402
from src.models import Experience, ExperienceCategory, Location, Provider  # noqa: E402


def _image(**overrides) -> WikimediaImage:
    defaults = dict(
        title="File:Grand Heritage Museum.jpg",
        page_id=1,
        image_url="https://upload.wikimedia.org/example.jpg",
        thumbnail_url="https://thumb.wikimedia.org/example_thumb.jpg",
        description_url="https://commons.wikimedia.org/wiki/File:Grand_Heritage_Museum.jpg",
        width=1600,
        height=1200,
        license="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0",
        author="Jane Doe",
        attribution_required=True,
        categories=["Grand Heritage Museum"],
        latitude=None,
        longitude=None,
        distance_km=None,
    )
    defaults.update(overrides)
    return WikimediaImage(**defaults)


class _FakeAdapter:
    def __init__(self, *, title_results=None):
        self._title_results = title_results or {}
        self.call_count = 0

    async def search_by_title(self, query, *, limit):
        self.call_count += 1
        return self._title_results.get(query, [])

    async def search_nearby(self, lat, lng, radius_m, *, limit):
        return []

    async def resolve_file(self, title):
        return None


async def _make_experience(session_factory) -> str:
    """Creates the fixture row and returns its id (not the ORM object —
    each test loads its own fresh, eager-loaded instance per session)."""
    async with session_factory() as session:
        category = ExperienceCategory(slug=CATEGORIES[0].slug, name=CATEGORIES[0].name, sort_order=0)
        session.add(category)
        await session.flush()

        provider = Provider(business_name="Grand Heritage Museum", is_synthetic=True)
        session.add(provider)
        location = Location(latitude=18.93, longitude=72.83, city="Mumbai", is_synthetic=True)
        session.add(location)
        await session.flush()

        experience = Experience(
            provider_id=provider.id,
            category_id=category.id,
            location_id=location.id,
            title="Grand Heritage Museum",
            short_description="A museum.",
            full_description="A museum, in full.",
            status="active",
            verification_status="unverified",
            opening_hours_status="unavailable",
            source_type="synthetic",
            is_synthetic=True,
        )
        session.add(experience)
        await session.commit()
        return experience.id


async def _load_experience(session, experience_id: str) -> Experience:
    result = await session.execute(
        select(Experience)
        .options(
            selectinload(Experience.provider),
            selectinload(Experience.location),
            selectinload(Experience.category),
        )
        .where(Experience.id == experience_id)
    )
    return result.scalars().one()


def test_enrichment_is_idempotent_on_second_run(session_factory) -> None:
    async def _run() -> None:
        experience_id = await _make_experience(session_factory)
        settings = Settings()
        exact = _image()
        adapter = _FakeAdapter(title_results={"Grand Heritage Museum": [exact]})
        rows: list = []

        async with session_factory() as session:
            experience = await _load_experience(session, experience_id)
            stats1: Counter = Counter()
            await _process_one(
                session, experience, adapter, settings, refresh=False, dry_run=False, stats=stats1, rows=rows
            )
            assert stats1[WIKIMEDIA_PLACE_SPECIFIC] == 1
            assert experience.image_url == exact.image_url
            first_call_count = adapter.call_count

        # Second run, fresh session/object load — must not re-query
        # Wikimedia or duplicate the write (idempotent).
        async with session_factory() as session:
            experience = await _load_experience(session, experience_id)
            stats2: Counter = Counter()
            await _process_one(
                session, experience, adapter, settings, refresh=False, dry_run=False, stats=stats2, rows=rows
            )
            assert stats2[EXISTING_VALID] == 1
            assert adapter.call_count == first_call_count  # no new Wikimedia calls

    asyncio.run(_run())


def test_provider_owned_image_never_overwritten(session_factory) -> None:
    async def _run() -> None:
        experience_id = await _make_experience(session_factory)
        exact = _image()
        adapter = _FakeAdapter(title_results={"Grand Heritage Museum": [exact]})
        settings = Settings()

        async with session_factory() as session:
            experience = await _load_experience(session, experience_id)
            experience.image_url = "https://provider-cdn.example.com/real-photo.jpg"
            experience.image_source = "provider_upload"
            await session.commit()

            stats: Counter = Counter()
            rows: list = []
            # Even with --refresh, provider_upload must never be touched.
            await _process_one(
                session, experience, adapter, settings, refresh=True, dry_run=False, stats=stats, rows=rows
            )

            assert stats[PROVIDER_OWNED] == 1
            assert experience.image_url == "https://provider-cdn.example.com/real-photo.jpg"
            assert experience.image_source == "provider_upload"
            assert adapter.call_count == 0  # never even queried

    asyncio.run(_run())


def test_refresh_flag_re_resolves_existing_wikimedia_image(session_factory) -> None:
    async def _run() -> None:
        experience_id = await _make_experience(session_factory)
        old_image = _image(
            title="File:Old Photo.jpg", description_url="https://commons.wikimedia.org/wiki/File:Old_Photo.jpg"
        )
        new_image = _image(
            title="File:New Photo.jpg", description_url="https://commons.wikimedia.org/wiki/File:New_Photo.jpg"
        )
        settings = Settings()

        async with session_factory() as session:
            experience = await _load_experience(session, experience_id)
            experience.image_url = old_image.image_url
            experience.image_source = "wikimedia_commons"
            await session.commit()

            adapter = _FakeAdapter(title_results={"Grand Heritage Museum": [new_image]})
            stats: Counter = Counter()
            rows: list = []
            await _process_one(
                session, experience, adapter, settings, refresh=True, dry_run=False, stats=stats, rows=rows
            )

            assert stats[WIKIMEDIA_PLACE_SPECIFIC] == 1
            assert adapter.call_count > 0  # actually re-queried Wikimedia, not skipped

    asyncio.run(_run())


def test_dry_run_never_writes_to_database(session_factory) -> None:
    async def _run() -> None:
        experience_id = await _make_experience(session_factory)
        exact = _image()
        adapter = _FakeAdapter(title_results={"Grand Heritage Museum": [exact]})
        settings = Settings()

        async with session_factory() as session:
            experience = await _load_experience(session, experience_id)
            stats: Counter = Counter()
            rows: list = []
            await _process_one(
                session, experience, adapter, settings, refresh=False, dry_run=True, stats=stats, rows=rows
            )

            assert stats[WIKIMEDIA_PLACE_SPECIFIC] == 1
            assert experience.image_url is None  # nothing written

    asyncio.run(_run())
