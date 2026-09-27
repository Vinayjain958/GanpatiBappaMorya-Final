"""Request/response schemas for /api/v1/location/* — geocoding, routing,
and nearby-POI discovery. See src/adapters/{geocoding,routing,poi}.py for
the normalized adapter-layer types these mirror."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Profile = Literal["driving", "walking", "cycling"]


class LocationSearchResponseItem(BaseModel):
    display_name: str
    lat: float
    lng: float
    city: str | None = None
    locality: str | None = None
    state: str | None = None
    country: str | None = None
    source: str = "nominatim"


class LocationSearchResponse(BaseModel):
    items: list[LocationSearchResponseItem]


class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    profile: Profile = "driving"
    include_geometry: bool = False


class RouteResponse(BaseModel):
    distance_km: float
    duration_minutes: float
    geometry: dict[str, Any] | None = None
    source: Literal["osrm", "haversine_estimate"]


class TravelTimeDestination(BaseModel):
    id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class TravelTimeMatrixRequest(BaseModel):
    origin: Coordinate
    destinations: list[TravelTimeDestination] = Field(min_length=1, max_length=25)
    profile: Profile = "driving"

    @field_validator("destinations")
    @classmethod
    def unique_ids(cls, value: list[TravelTimeDestination]) -> list[TravelTimeDestination]:
        ids = [d.id for d in value]
        if len(ids) != len(set(ids)):
            raise ValueError("destination ids must be unique")
        return value


class TravelTimeMatrixEntry(BaseModel):
    id: str
    distance_km: float | None
    duration_minutes: float | None


class TravelTimeMatrixResponse(BaseModel):
    source: Literal["osrm", "haversine_estimate"]
    profile: Profile
    destinations: list[TravelTimeMatrixEntry]


class NearbyPOIResponseItem(BaseModel):
    osm_type: str
    osm_id: int
    name: str
    category: str
    lat: float
    lng: float
    tags: dict[str, str]
    distance_km: float


class NearbyPOIResponse(BaseModel):
    items: list[NearbyPOIResponseItem]
    categories_available: list[str]
