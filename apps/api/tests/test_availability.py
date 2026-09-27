from __future__ import annotations

from tests.conftest import auth_header, register_provider


def _create_experience(client, body: dict, category_id: str) -> str:
    response = client.post(
        "/api/v1/experiences",
        headers=auth_header(body),
        json={
            "title": "Availability Test Experience",
            "short_description": "A short description here.",
            "full_description": "A longer description for the availability test experience.",
            "category_id": category_id,
            "location": {"latitude": 18.9, "longitude": 72.8, "city": "Mumbai"},
            "duration_minutes": 60,
            "capacity": 8,
            "status": "active",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_provider_can_create_availability(client, seeded_ids) -> None:
    body = register_provider(client, "avail-p1@example.com", "Avail Co 1")
    experience_id = _create_experience(client, body, seeded_ids["category_id"])

    response = client.post(
        f"/api/v1/experiences/{experience_id}/availability",
        headers=auth_header(body),
        json={"starts_at": "2026-10-10T14:00:00Z", "ends_at": "2026-10-10T15:30:00Z", "capacity": 8},
    )
    assert response.status_code == 201
    assert response.json()["capacity"] == 8
    assert response.json()["status"] == "active"


def test_availability_rejects_end_before_start(client, seeded_ids) -> None:
    body = register_provider(client, "avail-p2@example.com", "Avail Co 2")
    experience_id = _create_experience(client, body, seeded_ids["category_id"])

    response = client.post(
        f"/api/v1/experiences/{experience_id}/availability",
        headers=auth_header(body),
        json={"starts_at": "2026-10-10T15:30:00Z", "ends_at": "2026-10-10T14:00:00Z", "capacity": 8},
    )
    assert response.status_code == 422


def test_provider_can_update_own_availability(client, seeded_ids) -> None:
    body = register_provider(client, "avail-p3@example.com", "Avail Co 3")
    experience_id = _create_experience(client, body, seeded_ids["category_id"])
    create_resp = client.post(
        f"/api/v1/experiences/{experience_id}/availability",
        headers=auth_header(body),
        json={"starts_at": "2026-10-10T14:00:00Z", "ends_at": "2026-10-10T15:30:00Z", "capacity": 8},
    )
    availability_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/api/v1/experiences/{experience_id}/availability/{availability_id}",
        headers=auth_header(body),
        json={"capacity": 12},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["capacity"] == 12


def test_provider_can_deactivate_own_availability(client, seeded_ids) -> None:
    body = register_provider(client, "avail-p4@example.com", "Avail Co 4")
    experience_id = _create_experience(client, body, seeded_ids["category_id"])
    create_resp = client.post(
        f"/api/v1/experiences/{experience_id}/availability",
        headers=auth_header(body),
        json={"starts_at": "2026-10-10T14:00:00Z", "ends_at": "2026-10-10T15:30:00Z", "capacity": 8},
    )
    availability_id = create_resp.json()["id"]

    delete_resp = client.delete(
        f"/api/v1/experiences/{experience_id}/availability/{availability_id}",
        headers=auth_header(body),
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "inactive"


def test_provider_cannot_modify_another_providers_availability(client, seeded_ids) -> None:
    owner = register_provider(client, "avail-p5-owner@example.com", "Avail Owner Co")
    intruder = register_provider(client, "avail-p5-intruder@example.com", "Avail Intruder Co")
    experience_id = _create_experience(client, owner, seeded_ids["category_id"])
    create_resp = client.post(
        f"/api/v1/experiences/{experience_id}/availability",
        headers=auth_header(owner),
        json={"starts_at": "2026-10-10T14:00:00Z", "ends_at": "2026-10-10T15:30:00Z", "capacity": 8},
    )
    availability_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/api/v1/experiences/{experience_id}/availability/{availability_id}",
        headers=auth_header(intruder),
        json={"capacity": 99},
    )
    assert update_resp.status_code == 404

    delete_resp = client.delete(
        f"/api/v1/experiences/{experience_id}/availability/{availability_id}",
        headers=auth_header(intruder),
    )
    assert delete_resp.status_code == 404


def test_list_availability_is_public(client, seeded_ids) -> None:
    body = register_provider(client, "avail-p6@example.com", "Avail Co 6")
    experience_id = _create_experience(client, body, seeded_ids["category_id"])
    client.post(
        f"/api/v1/experiences/{experience_id}/availability",
        headers=auth_header(body),
        json={"starts_at": "2026-10-10T14:00:00Z", "ends_at": "2026-10-10T15:30:00Z", "capacity": 8},
    )

    response = client.get(f"/api/v1/experiences/{experience_id}/availability")
    assert response.status_code == 200
    assert len(response.json()) == 1
