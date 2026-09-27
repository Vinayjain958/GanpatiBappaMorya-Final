from __future__ import annotations

from tests.conftest import auth_header, register_provider, register_traveler


def _review(client, headers, experience_id, rating=5, title="Loved it", body="Great chai and kind people."):
    return client.post(
        f"/api/v1/experiences/{experience_id}/reviews",
        headers=headers,
        json={"rating_value": rating, "title": title, "body": body},
    )


def test_traveler_review_is_persisted_and_updates_rating(client, seeded_ids) -> None:
    body = register_traveler(client, "review-1@example.com")
    experience_id = seeded_ids["experience_id"]

    response = _review(client, auth_header(body), experience_id, rating=4)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["review"]["rating_value"] == 4
    assert payload["review"]["is_synthetic"] is False
    assert payload["review"]["author_display_name"] == "Review 1"
    assert payload["rating_summary"]["review_count"] >= 1

    reviews = client.get(f"/api/v1/experiences/{experience_id}/reviews").json()
    assert payload["review"]["id"] in [item["id"] for item in reviews["items"]]


def test_second_review_on_same_experience_does_not_collide(client, seeded_ids) -> None:
    experience_id = seeded_ids["experience_id"]
    first = _review(client, auth_header(register_traveler(client, "review-2a@example.com")), experience_id, rating=5)
    second = _review(client, auth_header(register_traveler(client, "review-2b@example.com")), experience_id, rating=3)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["rating_summary"]["review_count"] == first.json()["rating_summary"]["review_count"] + 1


def test_review_rating_shows_in_cached_listing(client, seeded_ids) -> None:
    experience_id = seeded_ids["experience_id"]
    assert client.get("/api/v1/experiences").status_code == 200  # prime the catalog cache

    response = _review(client, auth_header(register_traveler(client, "review-3@example.com")), experience_id, rating=1)
    assert response.status_code == 201, response.text

    listing = {item["id"]: item for item in client.get("/api/v1/experiences").json()["items"]}
    assert listing[experience_id]["review_count"] == response.json()["rating_summary"]["review_count"]


def test_review_requires_traveler(client, seeded_ids) -> None:
    experience_id = seeded_ids["experience_id"]
    assert _review(client, {}, experience_id).status_code == 401
    provider = register_provider(client, "review-prov@example.com", "Review Prov Co")
    assert _review(client, auth_header(provider), experience_id).status_code == 403


def test_review_validation(client, seeded_ids) -> None:
    headers = auth_header(register_traveler(client, "review-4@example.com"))
    assert _review(client, headers, seeded_ids["experience_id"], rating=6).status_code == 422
    assert _review(client, headers, seeded_ids["experience_id"], title="").status_code == 422
    assert _review(client, headers, "missing-experience").status_code == 404
