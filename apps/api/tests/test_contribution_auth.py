from __future__ import annotations

from tests.conftest import auth_header, register_provider, register_traveler
from tests.contribution_fixtures import submit_contribution


def test_unauthenticated_submission_rejected(client, seeded_ids) -> None:
    response = submit_contribution(client, {}, seeded_ids["category_id"])
    assert response.status_code == 401


def test_provider_cannot_submit_contribution(client, seeded_ids) -> None:
    body = register_provider(client, "contrib-provider@example.com", "Some Biz")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    assert response.status_code == 403


def test_authenticated_traveler_accepted(client, seeded_ids) -> None:
    body = register_traveler(client, "contrib-traveler1@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    assert response.status_code == 201, response.text
