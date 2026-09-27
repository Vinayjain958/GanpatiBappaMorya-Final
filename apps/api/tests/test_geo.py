from __future__ import annotations

import pytest

from src.core.geo import bounding_box, haversine_km, validate_coordinates


def test_haversine_known_distance_mumbai_to_pune() -> None:
    # Mumbai (CST) to Pune (Shivajinagar) — well-known ~120km straight-line.
    distance = haversine_km(18.9401, 72.8352, 18.5308, 73.8474)
    assert 115 < distance < 125


def test_haversine_zero_distance() -> None:
    assert haversine_km(18.93, 72.83, 18.93, 72.83) == 0


def test_haversine_symmetric() -> None:
    a = haversine_km(18.93, 72.83, 19.05, 72.85)
    b = haversine_km(19.05, 72.85, 18.93, 72.83)
    assert a == pytest.approx(b)


@pytest.mark.parametrize(
    ("lat1", "lng1", "lat2", "lng2"),
    [(91, 72.83, 18.93, 72.83), (18.93, 181, 18.93, 72.83), (18.93, 72.83, -91, 72.83)],
)
def test_haversine_rejects_invalid_coordinates(lat1, lng1, lat2, lng2) -> None:
    with pytest.raises(ValueError):
        haversine_km(lat1, lng1, lat2, lng2)


def test_validate_coordinates_accepts_valid() -> None:
    validate_coordinates(18.93, 72.83)  # should not raise


@pytest.mark.parametrize(("lat", "lng"), [(90.1, 0), (-90.1, 0), (0, 180.1), (0, -180.1)])
def test_validate_coordinates_rejects_out_of_range(lat, lng) -> None:
    with pytest.raises(ValueError):
        validate_coordinates(lat, lng)


def test_bounding_box_contains_center() -> None:
    box = bounding_box(18.93, 72.83, 5)
    assert box.min_lat < 18.93 < box.max_lat
    assert box.min_lng < 72.83 < box.max_lng


def test_bounding_box_width_scales_with_radius() -> None:
    small = bounding_box(18.93, 72.83, 1)
    large = bounding_box(18.93, 72.83, 10)
    assert (large.max_lat - large.min_lat) > (small.max_lat - small.min_lat)


def test_bounding_box_rejects_non_positive_radius() -> None:
    with pytest.raises(ValueError):
        bounding_box(18.93, 72.83, 0)


def test_bounding_box_clamped_near_pole() -> None:
    box = bounding_box(89.9, 0, 50)
    assert box.max_lat <= 90
