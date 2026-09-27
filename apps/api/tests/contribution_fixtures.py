"""Shared helpers for traveler-contribution tests."""

from __future__ import annotations

import io

from PIL import Image


def make_test_jpeg(color: tuple[int, int, int] = (200, 100, 50), size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


def make_contribution_form(category_id: str, **overrides) -> dict:
    form = {
        "name": "Fort Spice Corner",
        "category_id": category_id,
        "latitude": "18.9402",
        "longitude": "72.8347",
        "contact_phone": "+91 98765 43210",
    }
    form.update({k: str(v) for k, v in overrides.items()})
    return form


def submit_contribution(client, headers: dict, category_id: str, **overrides):
    image_bytes = overrides.pop("image_bytes", None) or make_test_jpeg()
    filename = overrides.pop("filename", "photo.jpg")
    content_type = overrides.pop("content_type", "image/jpeg")
    form = make_contribution_form(category_id, **overrides)
    return client.post(
        "/api/v1/contributions/experiences",
        headers=headers,
        data=form,
        files={"image": (filename, io.BytesIO(image_bytes), content_type)},
    )
