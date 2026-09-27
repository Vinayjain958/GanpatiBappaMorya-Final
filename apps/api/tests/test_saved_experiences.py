from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.conftest import auth_header, register_traveler


def _interaction(client, headers: dict, experience_id: str, event_type: str, event_id: str, second: int) -> None:
    occurred_at = (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=second)).isoformat()
    response = client.post(
        "/api/v1/feedback/interactions",
        headers=headers,
        json={
            "experience_id": experience_id,
            "event_type": event_type,
            "client_event_id": event_id,
            "occurred_at": occurred_at,
            "source": "experience_card",
        },
    )
    assert response.status_code == 200, response.text


def test_saved_experiences_empty_for_new_traveler(client, seeded_ids) -> None:
    traveler = register_traveler(client, "saved-empty@example.com")
    response = client.get("/api/v1/experiences/saved", headers=auth_header(traveler))

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_save_and_unsave_update_the_saved_list(client, seeded_ids) -> None:
    traveler = register_traveler(client, "saved-cycle@example.com")
    headers = auth_header(traveler)
    experience_id = seeded_ids["experience_id"]

    _interaction(client, headers, experience_id, "SAVE", "save-one", 1)
    saved = client.get("/api/v1/experiences/saved", headers=headers).json()
    assert [item["id"] for item in saved["items"]] == [experience_id]

    _interaction(client, headers, experience_id, "UNSAVE", "unsave-one", 2)
    unsaved = client.get("/api/v1/experiences/saved", headers=headers).json()
    assert unsaved["items"] == []

    _interaction(client, headers, experience_id, "SAVE", "save-two", 3)
    resaved = client.get("/api/v1/experiences/saved", headers=headers).json()
    assert [item["id"] for item in resaved["items"]] == [experience_id]


def test_saved_experiences_are_scoped_to_the_traveler(client, seeded_ids) -> None:
    traveler_a = register_traveler(client, "saved-owner@example.com")
    traveler_b = register_traveler(client, "saved-other@example.com")
    _interaction(
        client,
        auth_header(traveler_a),
        seeded_ids["experience_id"],
        "SAVE",
        "traveler-a-save",
        1,
    )

    response_a = client.get("/api/v1/experiences/saved", headers=auth_header(traveler_a))
    response_b = client.get("/api/v1/experiences/saved", headers=auth_header(traveler_b))
    assert response_a.json()["total"] == 1
    assert response_b.json()["total"] == 0


def test_saved_experiences_requires_traveler_authentication(client, seeded_ids) -> None:
    response = client.get("/api/v1/experiences/saved")
    assert response.status_code == 401


def test_saved_static_route_is_not_treated_as_an_experience_id(client, seeded_ids) -> None:
    traveler = register_traveler(client, "saved-route@example.com")
    response = client.get("/api/v1/experiences/saved", headers=auth_header(traveler))
    assert response.status_code == 200
    assert "items" in response.json()
