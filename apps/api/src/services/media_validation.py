"""Server-side image validation for traveler-uploaded experience photos.

Defense-in-depth — never trusts the client-supplied
filename or `Content-Type` header. The only thing that determines whether
an upload is accepted is whether Pillow can actually decode it as one of
the allowed formats. EXIF (including GPS) is always stripped by
re-encoding without it; the output is always re-encoded to JPEG so the
stored format is uniform regardless of the original.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageValidationError(ValueError):
    """Raised when uploaded bytes fail content validation. Message is
    safe to surface to the client (no internal detail leaked)."""


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    object_key: str
    content_type: str = "image/jpeg"


def validate_and_process_image(
    raw: bytes,
    *,
    max_bytes: int,
    max_dimension_px: int,
) -> ProcessedImage:
    if not raw:
        raise ImageValidationError("Please upload a valid JPG, PNG, or WebP image.")

    # Size check on raw bytes first — before any decode — so an oversized
    # upload can't even reach Pillow's decompression path.
    if len(raw) > max_bytes:
        raise ImageValidationError("Please upload a valid JPG, PNG, or WebP image.")

    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ImageValidationError("Please upload a valid JPG, PNG, or WebP image.") from None

    real_format = (probe.format or "").upper()
    if real_format not in _ALLOWED_FORMATS:
        raise ImageValidationError("Please upload a valid JPG, PNG, or WebP image.")

    # `verify()` closes the file handle and only checks structural
    # integrity — it does not decode pixel data, so a corrupt-but-
    # well-headed file can still slip through. Re-open and force a full
    # decode to catch that, and to actually process the image afterwards.
    try:
        opened = Image.open(io.BytesIO(raw))
        opened.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ImageValidationError("Please upload a valid JPG, PNG, or WebP image.") from None

    image: Image.Image = opened
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    width, height = image.size
    if max(width, height) > max_dimension_px:
        scale = max_dimension_px / max(width, height)
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS
        )

    # Re-encoding without an `exif` argument drops all EXIF metadata,
    # including GPS tags — no separate GPS-stripping step
    # needed since no metadata survives at all.
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=88, optimize=True)
    processed_bytes = buffer.getvalue()

    object_key = f"experiences/{uuid.uuid4().hex}.jpg"
    return ProcessedImage(data=processed_bytes, object_key=object_key)
