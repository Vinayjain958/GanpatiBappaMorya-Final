from __future__ import annotations

from tests.conftest import auth_header, register_provider


def _make_experience_payload(category_id: str, **overrides) -> dict:
    payload = {
        "title": "Fort Heritage Walk",
        "short_description": "A guided walk through Fort's landmarks.",
        "full_description": "A relaxed 90-minute guided walk covering the main heritage sites of Fort.",
        "category_id": category_id,
        "location": {"latitude": 18.934, "longitude": 72.835, "city": "Mumbai"},
        "price": 500,
        "duration_minutes": 90,
        "minimum_group_size": 1,
        "maximum_group_size": 10,
        "capacity": 10,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def test_provider_profile_retrieval_works(client) -> None:
    body = register_provider(client, "crud-p1@example.com", "CRUD Test Co")
    response = client.get("/api/v1/providers/me", headers=auth_header(body))
    assert response.status_code == 200
    assert response.json()["business_name"] == "CRUD Test Co"


def test_provider_profile_update_works(client) -> None:
    body = register_provider(client, "crud-p2@example.com", "Update Me Co")
    response = client.put(
        "/api/v1/providers/me",
        headers=auth_header(body),
        json={"description": "We run heritage walks.", "city": "Mumbai"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "We run heritage walks."
    assert response.json()["city"] == "Mumbai"


def test_provider_cannot_modify_protected_fields(client) -> None:
    body = register_provider(client, "crud-p3@example.com", "Protected Co")
    response = client.put(
        "/api/v1/providers/me",
        headers=auth_header(body),
        json={"verification_status": "verified"},
    )
    # verification_status is not part of ProviderUpdateRequest's schema —
    # FastAPI/Pydantic ignores unknown fields rather than applying them.
    assert response.status_code == 200
    assert response.json()["verification_status"] == "unverified"


def test_provider_can_create_experience(client, seeded_ids) -> None:
    body = register_provider(client, "crud-p4@example.com", "Create Co")
    response = client.post(
        "/api/v1/experiences",
        headers=auth_header(body),
        json=_make_experience_payload(seeded_ids["category_id"]),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Fort Heritage Walk"
    assert data["is_synthetic"] is False
    assert data["provider"]["business_name"] == "Create Co"


def test_provider_id_comes_from_auth_not_request_body(client, seeded_ids) -> None:
    body_a = register_provider(client, "crud-p5a@example.com", "Owner A")
    register_provider(client, "crud-p5b@example.com", "Owner B")  # decoy account

    payload = _make_experience_payload(seeded_ids["category_id"])
    payload["provider_id"] = "some-other-id-should-be-ignored"

    response = client.post("/api/v1/experiences", headers=auth_header(body_a), json=payload)
    assert response.status_code == 201
    assert response.json()["provider"]["business_name"] == "Owner A"
    assert response.json()["provider"]["business_name"] != "Owner B"


def test_provider_can_update_own_experience(client, seeded_ids) -> None:
    body = register_provider(client, "crud-p6@example.com", "Update Exp Co")
    create_resp = client.post(
        "/api/v1/experiences", headers=auth_header(body), json=_make_experience_payload(seeded_ids["category_id"])
    )
    experience_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/api/v1/experiences/{experience_id}",
        headers=auth_header(body),
        json={"title": "Fort Heritage Walk (Updated)"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Fort Heritage Walk (Updated)"


def test_provider_can_deactivate_own_experience(client, seeded_ids) -> None:
    body = register_provider(client, "crud-p7@example.com", "Deactivate Co")
    create_resp = client.post(
        "/api/v1/experiences", headers=auth_header(body), json=_make_experience_payload(seeded_ids["category_id"])
    )
    experience_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/experiences/{experience_id}", headers=auth_header(body))
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "inactive"


def test_provider_cannot_modify_another_providers_experience(client, seeded_ids) -> None:
    body_a = register_provider(client, "crud-p8a@example.com", "Owner A2")
    body_b = register_provider(client, "crud-p8b@example.com", "Owner B2")

    create_resp = client.post(
        "/api/v1/experiences", headers=auth_header(body_a), json=_make_experience_payload(seeded_ids["category_id"])
    )
    experience_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/experiences/{experience_id}", headers=auth_header(body_b), json={"title": "Hijacked"}
    )
    assert patch_resp.status_code == 404

    delete_resp = client.delete(f"/api/v1/experiences/{experience_id}", headers=auth_header(body_b))
    assert delete_resp.status_code == 404


def test_imported_catalog_experience_protected_from_provider_mutation(client, seeded_ids) -> None:
    body = register_provider(client, "crud-p9@example.com", "Unrelated Co")
    response = client.patch(
        f"/api/v1/experiences/{seeded_ids['experience_id']}",
        headers=auth_header(body),
        json={"title": "Hijacked catalog record"},
    )
    assert response.status_code == 404


def test_create_experience_rejects_invalid_group_size_range(client, seeded_ids) -> None:
    body = register_provider(client, "crud-p10@example.com", "Invalid Range Co")
    payload = _make_experience_payload(
        seeded_ids["category_id"], minimum_group_size=10, maximum_group_size=2
    )
    response = client.post("/api/v1/experiences", headers=auth_header(body), json=payload)
    assert response.status_code == 422


def test_create_experience_rejects_negative_price(client, seeded_ids) -> None:
    body = register_provider(client, "crud-p11@example.com", "Negative Price Co")
    payload = _make_experience_payload(seeded_ids["category_id"], price=-50)
    response = client.post("/api/v1/experiences", headers=auth_header(body), json=payload)
    assert response.status_code == 422
