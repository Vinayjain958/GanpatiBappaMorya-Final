from __future__ import annotations

import io

from PIL import Image

from src.api.v1 import contributions as contributions_api
from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import make_test_jpeg, submit_contribution


def test_uploaded_photo_is_served_from_the_database(client, seeded_ids) -> None:
    body = register_traveler(client, "media-1@example.com")
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"])
    assert response.status_code == 201, response.text

    image_url = response.json()["experience"]["image"]["url"]
    assert image_url.startswith("/api/v1/media/experiences/")

    served = client.get(image_url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert "immutable" in served.headers["cache-control"]
    assert Image.open(io.BytesIO(served.content)).format == "JPEG"


def test_media_route_rejects_unknown_and_traversal_keys(client) -> None:
    assert client.get("/api/v1/media/experiences/does-not-exist.jpg").status_code == 404
    assert client.get("/api/v1/media/experiences/../secrets.jpg").status_code == 404


def test_oversized_photo_is_downscaled(client, seeded_ids) -> None:
    body = register_traveler(client, "media-2@example.com")
    big = make_test_jpeg(size=(3000, 1500))
    response = submit_contribution(client, auth_header(body), seeded_ids["category_id"], image_bytes=big)
    assert response.status_code == 201, response.text

    served = client.get(response.json()["experience"]["image"]["url"])
    width, height = Image.open(io.BytesIO(served.content)).size
    assert max(width, height) <= 1600
    assert (width, height) == (1600, 800)


def test_failed_submissions_do_not_consume_rate_limit(client, seeded_ids, monkeypatch) -> None:
    monkeypatch.setattr(
        contributions_api, "_rate_limiter", contributions_api.SlidingWindowLimiter(max_calls=1)
    )
    body = register_traveler(client, "limit-1@example.com")
    headers = auth_header(body)

    for _ in range(3):
        failed = submit_contribution(client, headers, seeded_ids["category_id"], contact_phone="12")
        assert failed.status_code == 422

    first = submit_contribution(client, headers, seeded_ids["category_id"], name="Quota Test Cafe")
    assert first.status_code == 201, first.text

    second = submit_contribution(
        client, headers, seeded_ids["category_id"], name="Another Quota Cafe",
        latitude=19.2, longitude=72.9,
    )
    assert second.status_code == 429


def test_validation_error_message_is_readable(client, seeded_ids) -> None:
    body = register_traveler(client, "readable-1@example.com")
    response = submit_contribution(
        client, auth_header(body), seeded_ids["category_id"], website="instagram.com/spot"
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Website must start with http:// or https://"


def test_same_phone_as_community_contribution_is_blocked(client, seeded_ids) -> None:
    first_body = register_traveler(client, "phone-dup-1@example.com")
    first = submit_contribution(
        client, auth_header(first_body), seeded_ids["category_id"],
        name="Aunty's Vada Pav Stall", contact_phone="+91 98765 11111",
    )
    assert first.status_code == 201, first.text

    second_body = register_traveler(client, "phone-dup-2@example.com")
    second = submit_contribution(
        client, auth_header(second_body), seeded_ids["category_id"],
        name="Best Vada Pav Near Station", contact_phone="9876511111",
        latitude=18.9405, longitude=72.8350,
    )
    assert second.status_code == 409, second.text
    assert second.json()["existing_experience_id"] == first.json()["experience"]["id"]


def test_new_contribution_appears_in_cached_listing_with_source_type(client, seeded_ids) -> None:
    # Prime the catalog cache, then publish: the new place must still show up.
    assert client.get("/api/v1/experiences").status_code == 200

    body = register_traveler(client, "cache-1@example.com")
    response = submit_contribution(
        client, auth_header(body), seeded_ids["category_id"], name="Cache Busting Chai Point"
    )
    assert response.status_code == 201, response.text
    experience_id = response.json()["experience"]["id"]

    listing = client.get("/api/v1/experiences")
    items = {item["id"]: item for item in listing.json()["items"]}
    assert experience_id in items
    assert items[experience_id]["source_type"] == "traveler_submission"
