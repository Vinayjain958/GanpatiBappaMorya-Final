from __future__ import annotations

from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import submit_contribution


def test_published_experience_visible_in_catalog(client, seeded_ids) -> None:
    body = register_traveler(client, "pub-1@example.com")
    response = submit_contribution(
        client, auth_header(body), seeded_ids["category_id"], name="Unique Publish Test Cafe"
    )
    assert response.status_code == 201, response.text
    experience_id = response.json()["experience"]["id"]

    listing = client.get("/api/v1/experiences", params={"q": "Unique Publish Test Cafe"})
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["items"]]
    assert experience_id in ids

    detail = client.get(f"/api/v1/experiences/{experience_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "active"


def test_new_experience_starts_with_no_ratings(client, seeded_ids) -> None:
    body = register_traveler(client, "pub-2@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    experience = response.json()["experience"]
    assert experience["rating"] is None
    assert experience["review_count"] is None

    detail = client.get(f"/api/v1/experiences/{experience['id']}")
    assert detail.json()["rating_summary"]["review_count"] == 0
    assert detail.json()["rating_summary"]["average_rating"] is None


def test_uses_community_provider(client, seeded_ids) -> None:
    body = register_traveler(client, "pub-3@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    provider = response.json()["experience"]["provider"]
    assert provider["business_name"] == "LocaLens Community"
    assert provider["id"] == "00000000-0000-0000-0000-000000000001"


def test_invalid_category_leaves_no_orphan_location(client, seeded_ids, session_factory) -> None:
    import asyncio

    from sqlalchemy import func, select

    from src.models.location import Location

    body = register_traveler(client, "pub-4@example.com")

    async def count_locations() -> int:
        async with session_factory() as session:
            result = await session.execute(select(func.count(Location.id)))
            return result.scalar_one()

    before = asyncio.run(count_locations())
    response = submit_contribution(client, auth_header(body), "not-a-real-category")
    assert response.status_code == 422
    after = asyncio.run(count_locations())
    assert after == before
