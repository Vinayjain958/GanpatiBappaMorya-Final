from __future__ import annotations

from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import submit_contribution


def test_repeated_request_same_idempotency_key_does_not_double_publish(client, seeded_ids) -> None:
    body = register_traveler(client, "idem-1@example.com")
    headers = {**auth_header(body), "Idempotency-Key": "fixed-key-123"}

    first = submit_contribution(client, headers, seeded_ids["category_id"], name="Idempotent Place")
    assert first.status_code == 201, first.text
    second = submit_contribution(client, headers, seeded_ids["category_id"], name="Idempotent Place")
    assert second.status_code == 201, second.text

    assert first.json()["experience"]["id"] == second.json()["experience"]["id"]

    listing = client.get("/api/v1/experiences", params={"q": "Idempotent Place"})
    assert len(listing.json()["items"]) == 1


def test_different_idempotency_keys_publish_separately(client, seeded_ids) -> None:
    body = register_traveler(client, "idem-2@example.com")

    first = submit_contribution(
        client, {**auth_header(body), "Idempotency-Key": "key-a"}, seeded_ids["category_id"],
        name="Place A", latitude=18.9402, longitude=72.8347,
    )
    second = submit_contribution(
        client, {**auth_header(body), "Idempotency-Key": "key-b"}, seeded_ids["category_id"],
        name="Place B", latitude=19.2000, longitude=72.9000,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["experience"]["id"] != second.json()["experience"]["id"]
