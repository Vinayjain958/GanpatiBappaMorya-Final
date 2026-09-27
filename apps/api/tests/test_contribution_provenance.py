from __future__ import annotations

from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import submit_contribution


def test_provenance_fields_set_correctly(client, seeded_ids) -> None:
    body = register_traveler(client, "prov-1@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    assert response.status_code == 201, response.text
    experience = response.json()["experience"]

    assert experience["source_type"] == "traveler_submission"
    assert experience["is_synthetic"] is False
    assert experience["is_enriched"] is False
    assert experience["image"]["source"] == "traveler_upload"
    assert experience["image"]["is_synthetic"] is False


def test_contribution_linked_to_published_experience(client, seeded_ids) -> None:
    body = register_traveler(client, "prov-2@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    assert response.status_code == 201, response.text
    body_json = response.json()
    assert body_json["contribution"]["status"] == "published"
    assert body_json["contribution"]["id"]


def test_source_record_id_unique_per_experience(client, seeded_ids) -> None:
    body = register_traveler(client, "prov-3@example.com")
    first = submit_contribution(
        client, auth_header(body), seeded_ids["category_id"], name="Place A",
        latitude=18.9402, longitude=72.8347,
    )
    second = submit_contribution(
        client, auth_header(body), seeded_ids["category_id"], name="Place B",
        latitude=19.2000, longitude=72.9000,  # far away — not a duplicate candidate
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["experience"]["id"] != second.json()["experience"]["id"]
