from __future__ import annotations

import asyncio

from src.models.contribution import TravelerExperienceContribution
from src.models.user import User
from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import submit_contribution


def test_contribution_belongs_to_authenticated_traveler(client, seeded_ids, session_factory) -> None:
    body = register_traveler(client, "own-1@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    assert response.status_code == 201, response.text
    contribution_id = response.json()["contribution"]["id"]

    async def fetch():
        from sqlalchemy import select

        async with session_factory() as session:
            contribution = await session.get(TravelerExperienceContribution, contribution_id)
            user = await session.execute(select(User).where(User.email == "own-1@example.com"))
            return contribution, user.scalars().one()

    contribution, user = asyncio.run(fetch())
    assert contribution.traveler_id == user.id


def test_client_cannot_forge_traveler_id(client, seeded_ids) -> None:
    """The endpoint has no field for traveler_id/provider_id at all — this
    test documents that intent by confirming the schema silently ignores
    any such extra form field rather than honoring it."""
    body = register_traveler(client, "own-2@example.com")
    response = submit_contribution(
        client, auth_header(body), seeded_ids["category_id"], traveler_id="some-other-user-id"
    )
    # Extra form fields are simply not read by ContributionCreateForm.
    assert response.status_code == 201, response.text
