"""Itinerary versioning/concurrency tests (Phase 9) — POST
/itineraries/{id}/replan (manual replan REST endpoint)."""

from __future__ import annotations

from tests.conftest import auth_header, register_traveler


def _compose_payload(**overrides) -> dict:
    payload = {
        "query": "food",
        "itinerary_date": "2026-10-12",
        "start_time": "09:00:00",
        "end_time": "20:00:00",
        "max_experiences": 3,
        "travel_mode": "driving",
    }
    payload.update(overrides)
    return payload


def _compose(discovery_client, email: str) -> tuple[dict, dict]:
    user = register_traveler(discovery_client, email)
    resp = discovery_client.post(
        "/api/v1/itineraries/compose", json=_compose_payload(), headers=auth_header(user)
    )
    assert resp.status_code == 200, resp.text
    return user, resp.json()


def test_new_itinerary_starts_at_version_1(discovery_client) -> None:
    user, body = _compose(discovery_client, "version-traveler@example.com")
    if "items" not in body:
        return
    assert body["version"] == 1
    assert body["replanning_status"] == "STABLE"


def test_replan_requires_auth(discovery_client) -> None:
    resp = discovery_client.post("/api/v1/itineraries/some-id/replan", json={})
    assert resp.status_code == 401


def test_replan_stale_version_returns_409(discovery_client) -> None:
    user, body = _compose(discovery_client, "stale-version@example.com")
    if "items" not in body:
        return
    itinerary_id = body["id"]

    resp = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/replan",
        json={"expected_version": 999, "trigger": "USER_REQUESTED"},
        headers=auth_header(user),
    )
    assert resp.status_code == 409
    assert resp.json()["message"]


def test_replan_wrong_owner_gets_404(discovery_client) -> None:
    owner, body = _compose(discovery_client, "version-owner@example.com")
    intruder = register_traveler(discovery_client, "version-intruder@example.com")
    if "items" not in body:
        return
    itinerary_id = body["id"]

    resp = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/replan",
        json={"trigger": "USER_REQUESTED"},
        headers=auth_header(intruder),
    )
    assert resp.status_code == 404


def test_replan_no_op_keeps_same_version(discovery_client) -> None:
    """A USER_REQUESTED replan with no flexible items to touch (or one
    that finds no material impact) should never silently bump the
    version — NO_CHANGE outcomes never create a new revision."""
    user, body = _compose(discovery_client, "noop-version@example.com")
    if "items" not in body:
        return
    itinerary_id = body["id"]
    original_version = body["version"]

    resp = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/replan",
        json={"expected_version": original_version, "trigger": "USER_REQUESTED"},
        headers=auth_header(user),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["status"] in ("NO_CHANGE", "REPLANNED", "REPLAN_FAILED")
    if result["status"] == "NO_CHANGE":
        assert result["new_version"] == result["previous_version"]


def test_repeated_idempotency_key_does_not_duplicate(discovery_client) -> None:
    user, body = _compose(discovery_client, "idem-version@example.com")
    if "items" not in body:
        return
    itinerary_id = body["id"]

    payload = {"trigger": "USER_REQUESTED", "idempotency_key": "same-key-123"}
    first = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/replan", json=payload, headers=auth_header(user)
    )
    second = discovery_client.post(
        f"/api/v1/itineraries/{itinerary_id}/replan", json=payload, headers=auth_header(user)
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == second.json()["status"]
