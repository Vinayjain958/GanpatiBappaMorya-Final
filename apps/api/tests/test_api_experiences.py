from __future__ import annotations


def test_list_experiences_returns_seeded_row(client, seeded_ids) -> None:
    response = client.get("/api/v1/experiences")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded_ids["experience_id"]
    assert body["items"][0]["category"]["slug"] == "food-drink"


def test_list_experiences_category_filter_matches(client) -> None:
    response = client.get("/api/v1/experiences", params={"category": "food-drink"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_list_experiences_category_filter_excludes_non_matching(client) -> None:
    response = client.get("/api/v1/experiences", params={"category": "wellness"})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_list_experiences_pagination_params_respected(client) -> None:
    response = client.get("/api/v1/experiences", params={"limit": 1, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) <= 1


def test_get_experience_by_id_returns_full_detail(client, seeded_ids) -> None:
    response = client.get(f"/api/v1/experiences/{seeded_ids['experience_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Test Experience"
    assert body["full_description"]
    assert body["is_price_estimated"] is True
    assert "opening_hours" in body


def test_get_experience_missing_id_returns_404(client) -> None:
    response = client.get("/api/v1/experiences/does-not-exist")
    assert response.status_code == 404


def test_experience_response_never_exposes_password_hash(client, seeded_ids) -> None:
    response = client.get(f"/api/v1/experiences/{seeded_ids['experience_id']}")
    assert "password_hash" not in response.text
