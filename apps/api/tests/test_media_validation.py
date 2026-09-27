from __future__ import annotations

import io

import pytest
from PIL import Image

from src.services.media_validation import ImageValidationError, validate_and_process_image

_MAX_BYTES = 8 * 1024 * 1024
_MAX_DIM = 2000


def _jpeg_bytes(size=(50, 50), color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes(size=(50, 50), color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def _webp_bytes(size=(50, 50), color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="WEBP")
    return buf.getvalue()


def test_valid_jpeg_accepted() -> None:
    result = validate_and_process_image(_jpeg_bytes(), max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)
    assert result.object_key.startswith("experiences/")
    assert result.object_key.endswith(".jpg")
    # Output always decodes cleanly as JPEG.
    Image.open(io.BytesIO(result.data)).verify()


def test_valid_png_accepted_and_reencoded_to_jpeg() -> None:
    result = validate_and_process_image(_png_bytes(), max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)
    reopened = Image.open(io.BytesIO(result.data))
    assert reopened.format == "JPEG"


def test_valid_webp_accepted() -> None:
    result = validate_and_process_image(_webp_bytes(), max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)
    Image.open(io.BytesIO(result.data)).verify()


def test_svg_rejected() -> None:
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    with pytest.raises(ImageValidationError):
        validate_and_process_image(svg, max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)


def test_html_rejected() -> None:
    html = b"<html><body>not an image</body></html>"
    with pytest.raises(ImageValidationError):
        validate_and_process_image(html, max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)


def test_empty_bytes_rejected() -> None:
    with pytest.raises(ImageValidationError):
        validate_and_process_image(b"", max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)


def test_oversized_bytes_rejected() -> None:
    huge = b"\xff\xd8\xff" + b"0" * (_MAX_BYTES + 1)
    with pytest.raises(ImageValidationError):
        validate_and_process_image(huge, max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)


def test_exif_stripped() -> None:
    # Build a JPEG with EXIF data attached, then confirm the processed
    # output has none.
    buf = io.BytesIO()
    img = Image.new("RGB", (50, 50), color=(1, 2, 3))
    exif = img.getexif()
    exif[0x0110] = "Test Camera"  # Model tag
    img.save(buf, format="JPEG", exif=exif)
    raw = buf.getvalue()

    # Sanity-check the input actually carries EXIF before processing.
    assert Image.open(io.BytesIO(raw)).getexif()

    result = validate_and_process_image(raw, max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)
    reopened = Image.open(io.BytesIO(result.data))
    assert not reopened.getexif()


def test_downscaled_to_max_dimension() -> None:
    large = _jpeg_bytes(size=(4000, 100))
    result = validate_and_process_image(large, max_bytes=_MAX_BYTES, max_dimension_px=500)
    reopened = Image.open(io.BytesIO(result.data))
    assert max(reopened.size) <= 500


def test_object_keys_are_unique() -> None:
    a = validate_and_process_image(_jpeg_bytes(), max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)
    b = validate_and_process_image(_jpeg_bytes(), max_bytes=_MAX_BYTES, max_dimension_px=_MAX_DIM)
    assert a.object_key != b.object_key
