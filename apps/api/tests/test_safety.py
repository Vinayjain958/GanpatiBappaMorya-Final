import pytest
from src.models.safety import EmergencyAlert, EmergencyContact

def register_traveler(client, email: str, password: str = "supersecret123", **extra) -> dict:
    payload = {
        "email": email,
        "password": password,
        "role": "traveler",
        "display_name": "Test Traveler",
        **extra,
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def auth_header(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['access_token']}"}

@pytest.fixture
def contact_payload():
    return {
        "name": "Jane Doe",
        "phone": "555-1234",
        "relationship": "Sister",
        "is_primary": True
    }

@pytest.fixture
def alert_payload():
    return {
        "trigger_source": "manual_button",
        "message": "Need help",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "location_shared": True,
        "idempotency_key": "test_idemp_key_1"
    }

def test_create_emergency_contact(client, contact_payload):
    user_data = register_traveler(client, email="traveler1@test.com")
    headers = auth_header(user_data)

    response = client.post("/api/v1/safety/emergency-contacts", json=contact_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == contact_payload["name"]
    assert data["is_primary"] is True

def test_emergency_alert_idempotency(client, alert_payload):
    user_data = register_traveler(client, email="traveler2@test.com")
    headers = auth_header(user_data)

    # First request
    response1 = client.post("/api/v1/safety/emergency-alerts", json=alert_payload, headers=headers)
    assert response1.status_code == 201
    alert1 = response1.json()

    # Second request with same idempotency key
    response2 = client.post("/api/v1/safety/emergency-alerts", json=alert_payload, headers=headers)
    assert response2.status_code == 201
    alert2 = response2.json()

    # Should return the exact same alert
    assert alert1["id"] == alert2["id"]

    # Different payload with same idempotency key should conflict
    alert_payload_modified = alert_payload.copy()
    alert_payload_modified["message"] = "Different message"
    response3 = client.post("/api/v1/safety/emergency-alerts", json=alert_payload_modified, headers=headers)
    assert response3.status_code == 409

def test_get_nearby_resources_explicit_fallback_mode(client, monkeypatch):
    # Deterministic: forces the seed adapter via SAFETY_RESOURCES_MODE
    # rather than depending on the real Overpass network call failing
    # (live/auto-fallback behavior is covered by
    # tests/test_safety_resource_adapters.py against a fake HTTP client).
    from src.core.config import get_settings

    monkeypatch.setenv("SAFETY_RESOURCES_MODE", "fallback")
    get_settings.cache_clear()
    try:
        user_data = register_traveler(client, email="traveler3@test.com")
        headers = auth_header(user_data)

        response = client.get("/api/v1/safety/resources/nearby?lat=40.7128&lng=-74.0060&radius_km=10", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["is_synthetic"] is True

        types = [d["type"] for d in data]
        assert "hospital" in types
        assert "police" in types
        assert "consulate" in types
    finally:
        get_settings.cache_clear()
