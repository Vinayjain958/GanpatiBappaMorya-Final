from __future__ import annotations

from tests.conftest import FORT_LAT, FORT_LNG


def test_keyword_search_matches_title(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"q": "heritage"})
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()["items"]]
    assert "Fort Heritage Food Trail" in titles
    # Inactive experiences must never appear in default (active-only) discovery.
    assert "Inactive Heritage Tour" not in titles


def test_keyword_search_no_match_returns_empty(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"q": "zzzznonexistentzzzz"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_category_filter(discovery_client, discovery_dataset) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"category": "food-drink"})
    assert response.status_code == 200
    titles = {i["title"] for i in response.json()["items"]}
    assert titles == {"Fort Heritage Food Trail", "Andheri Street Snacks"}


def test_city_filter(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"city": "Mumbai"})
    assert response.status_code == 200
    assert response.json()["total"] == 3  # 3 active; the inactive one is excluded by default


def test_locality_filter(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"locality": "Andheri"})
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()["items"]]
    assert titles == ["Andheri Street Snacks"]


def test_price_range_filter(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"min_price": 200, "max_price": 400})
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()["items"]]
    assert titles == ["Fort Heritage Food Trail"]


def test_duration_range_filter(discovery_client) -> None:
    response = discovery_client.get(
        "/api/v1/experiences", params={"min_duration_minutes": 60, "max_duration_minutes": 180}
    )
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()["items"]]
    assert titles == ["Byculla Museum Walk"]


def test_pagination_limit_and_offset(discovery_client) -> None:
    first_page = discovery_client.get("/api/v1/experiences", params={"limit": 1, "offset": 0})
    second_page = discovery_client.get("/api/v1/experiences", params={"limit": 1, "offset": 1})
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]


def test_combined_filters(discovery_client) -> None:
    response = discovery_client.get(
        "/api/v1/experiences", params={"category": "food-drink", "max_price": 200}
    )
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()["items"]]
    assert titles == ["Andheri Street Snacks"]


def test_radius_filter_excludes_far_experience(discovery_client) -> None:
    response = discovery_client.get(
        "/api/v1/experiences", params={"lat": FORT_LAT, "lng": FORT_LNG, "radius_km": 3}
    )
    assert response.status_code == 200
    titles = {i["title"] for i in response.json()["items"]}
    assert "Andheri Street Snacks" not in titles  # ~15km away
    assert "Fort Heritage Food Trail" in titles  # ~0.1km away


def test_distance_km_present_for_location_query(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"lat": FORT_LAT, "lng": FORT_LNG})
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["distance_km"] is not None


def test_distance_km_absent_without_location_query(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["distance_km"] is None


def test_sort_by_distance(discovery_client) -> None:
    response = discovery_client.get(
        "/api/v1/experiences", params={"lat": FORT_LAT, "lng": FORT_LNG, "sort": "distance"}
    )
    assert response.status_code == 200
    distances = [i["distance_km"] for i in response.json()["items"]]
    assert distances == sorted(distances)


def test_sort_by_price(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"sort": "price"})
    assert response.status_code == 200
    prices = [i["price"] for i in response.json()["items"]]
    assert prices == sorted(prices)


def test_sort_distance_without_location_rejected(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"sort": "distance"})
    assert response.status_code == 422


def test_radius_without_location_rejected(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"radius_km": 5})
    assert response.status_code == 422


def test_radius_over_max_rejected(discovery_client) -> None:
    response = discovery_client.get(
        "/api/v1/experiences", params={"lat": FORT_LAT, "lng": FORT_LNG, "radius_km": 9999}
    )
    assert response.status_code == 422


def test_invalid_latitude_rejected(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"lat": 999, "lng": FORT_LNG})
    assert response.status_code == 422


def test_status_filter_can_include_inactive(discovery_client) -> None:
    response = discovery_client.get("/api/v1/experiences", params={"status": "inactive"})
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()["items"]]
    assert titles == ["Inactive Heritage Tour"]
