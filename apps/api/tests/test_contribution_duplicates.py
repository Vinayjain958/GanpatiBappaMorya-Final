from __future__ import annotations

import asyncio

from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.location import Location
from src.models.provider import Provider
from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import submit_contribution


def _seed_existing_experience(
    session_factory, *, title: str, lat: float, lng: float, phone: str | None = None, website: str | None = None
) -> dict[str, str]:
    async def _seed() -> dict[str, str]:
        async with session_factory() as session:
            category = ExperienceCategory(slug="dup-cat", name="Dup Category", sort_order=1)
            session.add(category)
            await session.flush()

            location = Location(
                latitude=lat, longitude=lng, city="Mumbai", locality="Fort",
                source_type="overture_places", is_synthetic=False,
            )
            session.add(location)

            provider = Provider(
                business_name="Existing Biz", verification_status="catalog_imported",
                source_type="overture_places", is_synthetic=False,
                contact_phone=phone, website=website,
            )
            session.add(provider)
            await session.flush()

            experience = Experience(
                provider=provider, category=category, location=location,
                title=title, short_description="An existing place.",
                full_description="An existing place, already in the catalog.",
                status="active", verification_status="catalog_imported",
                opening_hours_status="unavailable",
                source_type="overture_places", source_record_id="dup-rec-1",
                is_synthetic=False, is_enriched=True,
            )
            session.add(experience)
            await session.commit()
            return {"category_id": category.id, "experience_id": experience.id}

    return asyncio.run(_seed())


def test_exact_duplicate_blocked(client, session_factory) -> None:
    existing = _seed_existing_experience(
        session_factory, title="Fort Spice Corner", lat=18.9402, lng=72.8347
    )
    body = register_traveler(client, "dup-1@example.com")
    response = submit_contribution(
        client, auth_header(body), existing["category_id"], name="Fort Spice Corner",
        latitude=18.9403, longitude=72.8348,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "DUPLICATE_EXPERIENCE"
    assert response.json()["existing_experience_id"] == existing["experience_id"]


def test_same_phone_nearby_blocked(client, session_factory) -> None:
    existing = _seed_existing_experience(
        session_factory, title="Totally Different Name", lat=18.9402, lng=72.8347, phone="9876543210",
    )
    body = register_traveler(client, "dup-2@example.com")
    response = submit_contribution(
        client, auth_header(body), existing["category_id"], name="Another Name Entirely",
        latitude=18.9403, longitude=72.8348, contact_phone="+91 98765 43210",
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "DUPLICATE_EXPERIENCE"


def test_uncertain_duplicate_surfaced_without_publishing(client, session_factory) -> None:
    existing = _seed_existing_experience(
        session_factory, title="Fort Spice Corner Cafe", lat=18.9402, lng=72.8347
    )
    body = register_traveler(client, "dup-3@example.com")
    # Similar-but-not-identical name, a bit further away — should land in
    # the "uncertain" tier rather than "strong".
    response = submit_contribution(
        client, auth_header(body), existing["category_id"], name="Fort Spice Corner",
        latitude=18.9420, longitude=72.8365,
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "POSSIBLE_DUPLICATE"

    listing = client.get("/api/v1/experiences", params={"q": "Fort Spice Corner"})
    titles = [item["title"] for item in listing.json()["items"]]
    assert titles.count("Fort Spice Corner") == 0  # not published yet


def test_override_uncertain_duplicate_publishes(client, session_factory) -> None:
    existing = _seed_existing_experience(
        session_factory, title="Fort Spice Corner Cafe", lat=18.9402, lng=72.8347
    )
    body = register_traveler(client, "dup-4@example.com")
    response = submit_contribution(
        client, auth_header(body), existing["category_id"], name="Fort Spice Corner",
        latitude=18.9420, longitude=72.8365, override_duplicate_check=True,
    )
    assert response.status_code == 201, response.text
    assert response.json()["experience"]["title"] == "Fort Spice Corner"


def test_unrelated_place_not_flagged(client, session_factory) -> None:
    existing = _seed_existing_experience(
        session_factory, title="Fort Spice Corner", lat=18.9402, lng=72.8347
    )
    body = register_traveler(client, "dup-5@example.com")
    response = submit_contribution(
        client, auth_header(body), existing["category_id"], name="Completely Unrelated Bakery",
        latitude=19.2, longitude=72.9,  # far away
    )
    assert response.status_code == 201, response.text
