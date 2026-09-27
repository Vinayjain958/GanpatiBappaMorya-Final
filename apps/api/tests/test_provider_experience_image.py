from __future__ import annotations

import io

from PIL import Image

from tests.conftest import auth_header, register_provider
from tests.test_provider_crud import _make_experience_payload


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(20, 40, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _create_experience(client, headers: dict, seeded_ids) -> str:
    response = client.post(
        "/api/v1/experiences",
        headers=headers,
        json=_make_experience_payload(seeded_ids["category_id"]),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_provider_can_upload_shop_image(client, seeded_ids) -> None:
    body = register_provider(client, "img-p1@example.com", "Image Test Co")
    headers = auth_header(body)
    experience_id = _create_experience(client, headers, seeded_ids)

    response = client.post(
        f"/api/v1/experiences/{experience_id}/image",
        headers=headers,
        files={"image": ("shop.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["image"]["url"] is not None
    assert detail["image"]["source"] == "provider_upload"
    assert detail["image"]["is_synthetic"] is False


def test_upload_requires_authentication(client, seeded_ids) -> None:
    body = register_provider(client, "img-p2@example.com", "Image Test Co 2")
    experience_id = _create_experience(client, auth_header(body), seeded_ids)

    response = client.post(
        f"/api/v1/experiences/{experience_id}/image",
        files={"image": ("shop.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
    )
    assert response.status_code == 401


def test_provider_cannot_upload_image_for_experience_they_dont_own(client, seeded_ids) -> None:
    owner_body = register_provider(client, "img-p3-owner@example.com", "Owner Co")
    experience_id = _create_experience(client, auth_header(owner_body), seeded_ids)

    other_body = register_provider(client, "img-p3-other@example.com", "Other Co")
    response = client.post(
        f"/api/v1/experiences/{experience_id}/image",
        headers=auth_header(other_body),
        files={"image": ("shop.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
    )
    assert response.status_code == 404


def test_invalid_image_bytes_rejected(client, seeded_ids) -> None:
    body = register_provider(client, "img-p4@example.com", "Image Test Co 4")
    headers = auth_header(body)
    experience_id = _create_experience(client, headers, seeded_ids)

    response = client.post(
        f"/api/v1/experiences/{experience_id}/image",
        headers=headers,
        files={"image": ("shop.jpg", io.BytesIO(b"not an image"), "image/jpeg")},
    )
    assert response.status_code == 422


def test_uploaded_image_replaces_previous_one(client, seeded_ids) -> None:
    body = register_provider(client, "img-p5@example.com", "Image Test Co 5")
    headers = auth_header(body)
    experience_id = _create_experience(client, headers, seeded_ids)

    first = client.post(
        f"/api/v1/experiences/{experience_id}/image",
        headers=headers,
        files={"image": ("shop.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
    )
    second = client.post(
        f"/api/v1/experiences/{experience_id}/image",
        headers=headers,
        files={"image": ("shop2.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["image"]["url"] != second.json()["image"]["url"]
    # The replaced photo is removed from storage; the new one is served.
    assert client.get(first.json()["image"]["url"]).status_code == 404
    assert client.get(second.json()["image"]["url"]).status_code == 200
