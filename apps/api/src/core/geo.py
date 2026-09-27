"""Portable geospatial utilities — no PostGIS, no SQLite-specific spatial
extensions (docs/DECISIONS.md ADR-006/ADR-023). Distance is computed in
Python, not the database, so the same code runs on SQLite and PostgreSQL.

Haversine gives a straight-line ("as the crow flies") distance — it is
NOT travel time or travel distance. Callers must not present it as routing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088


def validate_latitude(lat: float) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")


def validate_longitude(lng: float) -> None:
    if not -180 <= lng <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lng}")


def validate_coordinates(lat: float, lng: float) -> None:
    validate_latitude(lat)
    validate_longitude(lng)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance between two points, in kilometers."""
    validate_coordinates(lat1, lng1)
    validate_coordinates(lat2, lng2)

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_KM * c


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


def bounding_box(lat: float, lng: float, radius_km: float) -> BoundingBox:
    """A conservative lat/lng box fully containing the radius circle —
    used to pre-filter candidate rows at the SQL layer before an exact
    Haversine check narrows them down in the application layer."""
    validate_coordinates(lat, lng)
    if radius_km <= 0:
        raise ValueError(f"radius_km must be positive, got {radius_km}")

    lat_delta = radius_km / 111.045  # ~km per degree latitude, roughly constant
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)  # guard the poles
    lng_delta = radius_km / (111.045 * cos_lat)

    return BoundingBox(
        min_lat=max(lat - lat_delta, -90),
        max_lat=min(lat + lat_delta, 90),
        min_lng=max(lng - lng_delta, -180),
        max_lng=min(lng + lng_delta, 180),
    )
