from __future__ import annotations

from tests.conftest import auth_header, register_traveler
from tests.contribution_fixtures import submit_contribution


def _traveler_headers(client, email: str) -> dict:
    body = register_traveler(client, email)
    return auth_header(body)


def test_invalid_image_bytes_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-1@example.com")
    response = submit_contribution(
        client, headers, seeded_ids["category_id"], image_bytes=b"not an image at all"
    )
    assert response.status_code == 422
    assert "valid" in response.json()["message"].lower()


def test_html_disguised_as_image_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-2@example.com")
    payload = b"<html><script>alert(1)</script></html>"
    response = submit_contribution(
        client, headers, seeded_ids["category_id"], image_bytes=payload, filename="photo.jpg"
    )
    assert response.status_code == 422


def test_oversized_image_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-3@example.com")
    # A real (small) JPEG padded past a tiny configured limit would be the
    # realistic test, but the max is 8MB by default — instead exercise the
    # raw-byte-length short-circuit directly with an oversized junk blob,
    # which the validator rejects before ever attempting to decode it.
    huge = b"\xff\xd8\xff" + b"0" * (9 * 1024 * 1024)
    response = submit_contribution(client, headers, seeded_ids["category_id"], image_bytes=huge)
    assert response.status_code == 422


def test_missing_name_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-4@example.com")
    response = submit_contribution(client, headers, seeded_ids["category_id"], name="")
    assert response.status_code == 422


def test_missing_phone_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-5@example.com")
    response = submit_contribution(client, headers, seeded_ids["category_id"], contact_phone="")
    assert response.status_code == 422


def test_invalid_coordinates_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-6@example.com")
    response = submit_contribution(client, headers, seeded_ids["category_id"], latitude=999)
    assert response.status_code == 422


def test_invalid_category_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-7@example.com")
    response = submit_contribution(client, headers, "not-a-real-category-id")
    assert response.status_code == 422


def test_invalid_website_scheme_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-8@example.com")
    response = submit_contribution(
        client, headers, seeded_ids["category_id"], website="javascript:alert(1)"
    )
    assert response.status_code == 422


def test_script_injection_in_description_stored_as_literal_text(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-9@example.com")
    malicious = "<script>alert('xss')</script>"
    response = submit_contribution(client, headers, seeded_ids["category_id"], description=malicious)
    assert response.status_code == 201, response.text
    # Stored/returned as inert text, never executed/interpreted — the API
    # is JSON, so this only matters for how the frontend renders it later,
    # but the backend must not strip/alter it into something else either.
    assert response.json()["experience"]["full_description"] == malicious


def test_junk_repeated_character_name_rejected(client, seeded_ids) -> None:
    headers = _traveler_headers(client, "val-10@example.com")
    response = submit_contribution(client, headers, seeded_ids["category_id"], name="aaaaaaaaaaaaaaaa")
    assert response.status_code == 422
