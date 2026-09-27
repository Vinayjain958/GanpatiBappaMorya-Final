from __future__ import annotations

from tests.conftest import auth_header, register_provider, register_traveler


def test_unauthenticated_protected_route_rejected(client) -> None:
    response = client.get("/api/v1/providers/me")
    assert response.status_code == 401


def test_traveler_cannot_access_provider_mutation_route(client) -> None:
    body = register_traveler(client, "trav-auth@example.com")
    response = client.get("/api/v1/providers/me", headers=auth_header(body))
    assert response.status_code == 403


def test_traveler_cannot_create_experience(client, seeded_ids) -> None:
    body = register_traveler(client, "trav-create@example.com")
    response = client.post(
        "/api/v1/experiences",
        headers=auth_header(body),
        json={
            "title": "Should not work",
            "short_description": "1234567890",
            "full_description": "1234567890",
            "category_id": seeded_ids["category_id"],
            "location": {"latitude": 1, "longitude": 1},
        },
    )
    assert response.status_code == 403


def test_provider_can_access_own_profile_route(client) -> None:
    body = register_provider(client, "prov-auth@example.com", "Auth Test Co")
    response = client.get("/api/v1/providers/me", headers=auth_header(body))
    assert response.status_code == 200
