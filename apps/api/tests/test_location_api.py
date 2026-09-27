from __future__ import annotations


def test_search_location_returns_200_with_mock_adapter(client) -> None:
    response = client.get("/api/v1/location/search", params={"q": "Fort Mumbai"})
    assert response.status_code == 200
    assert response.json()["items"] == []  # MockGeocodingAdapter returns nothing


def test_search_location_requires_min_length(client) -> None:
    response = client.get("/api/v1/location/search", params={"q": "a"})
    assert response.status_code == 422


def test_reverse_geocode_returns_200(client) -> None:
    response = client.get("/api/v1/location/reverse", params={"lat": 18.93, "lng": 72.83})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_reverse_geocode_rejects_invalid_latitude(client) -> None:
    response = client.get("/api/v1/location/reverse", params={"lat": 999, "lng": 72.83})
    assert response.status_code == 422


def test_nearby_pois_returns_200(client) -> None:
    response = client.get(
        "/api/v1/location/nearby-pois", params={"lat": 18.93, "lng": 72.83, "radius_m": 300, "categories": "cafe"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert "cafe" in response.json()["categories_available"]


def test_nearby_pois_rejects_unknown_category(client) -> None:
    response = client.get(
        "/api/v1/location/nearby-pois",
        params={"lat": 18.93, "lng": 72.83, "radius_m": 300, "categories": "not-a-category"},
    )
    assert response.status_code == 422


def test_nearby_pois_rejects_radius_over_max(client) -> None:
    response = client.get(
        "/api/v1/location/nearby-pois",
        params={"lat": 18.93, "lng": 72.83, "radius_m": 999999, "categories": "cafe"},
    )
    assert response.status_code == 422


def test_route_endpoint_returns_haversine_estimate_from_mock(client) -> None:
    response = client.post(
        "/api/v1/location/route",
        json={
            "origin": {"lat": 18.9346, "lng": 72.8356},
            "destination": {"lat": 18.9414, "lng": 72.8317},
            "profile": "driving",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "haversine_estimate"
    assert body["distance_km"] > 0
    assert body["duration_minutes"] > 0


def test_route_endpoint_rejects_invalid_profile(client) -> None:
    response = client.post(
        "/api/v1/location/route",
        json={
            "origin": {"lat": 18.9346, "lng": 72.8356},
            "destination": {"lat": 18.9414, "lng": 72.8317},
            "profile": "teleport",
        },
    )
    assert response.status_code == 422


def test_travel_time_matrix_returns_estimates(client) -> None:
    response = client.post(
        "/api/v1/location/travel-time-matrix",
        json={
            "origin": {"lat": 18.9346, "lng": 72.8356},
            "destinations": [
                {"id": "a", "lat": 18.9414, "lng": 72.8317},
                {"id": "b", "lat": 18.9067, "lng": 72.8147},
            ],
            "profile": "driving",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "haversine_estimate"
    assert {d["id"] for d in body["destinations"]} == {"a", "b"}


def test_travel_time_matrix_rejects_too_many_destinations(client) -> None:
    destinations = [{"id": str(i), "lat": 18.9, "lng": 72.8} for i in range(30)]
    response = client.post(
        "/api/v1/location/travel-time-matrix",
        json={"origin": {"lat": 18.9346, "lng": 72.8356}, "destinations": destinations, "profile": "driving"},
    )
    assert response.status_code == 422


def test_travel_time_matrix_rejects_duplicate_destination_ids(client) -> None:
    response = client.post(
        "/api/v1/location/travel-time-matrix",
        json={
            "origin": {"lat": 18.9346, "lng": 72.8356},
            "destinations": [
                {"id": "dup", "lat": 18.9414, "lng": 72.8317},
                {"id": "dup", "lat": 18.9067, "lng": 72.8147},
            ],
            "profile": "driving",
        },
    )
    assert response.status_code == 422


def test_travel_time_matrix_rejects_empty_destinations(client) -> None:
    response = client.post(
        "/api/v1/location/travel-time-matrix",
        json={"origin": {"lat": 18.9346, "lng": 72.8356}, "destinations": [], "profile": "driving"},
    )
    assert response.status_code == 422
