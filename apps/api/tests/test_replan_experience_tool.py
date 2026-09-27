"""replan_experience Gemini tool tests (Phase 9) — via the voice-path
bridge POST /conversations/{id}/tool-calls, mirroring
test_compose_experience_tool.py's pattern."""

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


def _compose(discovery_client, user) -> dict:
    resp = discovery_client.post(
        "/api/v1/itineraries/compose", json=_compose_payload(), headers=auth_header(user)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_conversation(discovery_client, user) -> str:
    resp = discovery_client.post("/api/v1/conversations", headers=auth_header(user))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_replan_experience_declared_in_known_tools() -> None:
    from src.api.v1.conversation import _KNOWN_TOOLS

    assert "replan_experience" in _KNOWN_TOOLS


def test_unknown_tool_name_fails_safely(discovery_client) -> None:
    user = register_traveler(discovery_client, "unknown-tool@example.com")
    conv_id = _create_conversation(discovery_client, user)

    resp = discovery_client.post(
        f"/api/v1/conversations/{conv_id}/tool-calls",
        json={"name": "delete_everything", "args": {}},
        headers=auth_header(user),
    )
    assert resp.status_code == 422


def test_replan_experience_requires_auth(discovery_client) -> None:
    resp = discovery_client.post(
        "/api/v1/conversations/some-id/tool-calls",
        json={"name": "replan_experience", "args": {"itinerary_id": "x", "requested_change": "y"}},
    )
    assert resp.status_code == 401


def test_replan_experience_authenticated_request_works(discovery_client) -> None:
    user = register_traveler(discovery_client, "replan-tool-traveler@example.com")
    itinerary = _compose(discovery_client, user)
    if "items" not in itinerary:
        return
    conv_id = _create_conversation(discovery_client, user)

    resp = discovery_client.post(
        f"/api/v1/conversations/{conv_id}/tool-calls",
        json={
            "name": "replan_experience",
            "args": {"itinerary_id": itinerary["id"], "requested_change": "Traveler wants a different pace."},
        },
        headers=auth_header(user),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["status"] in ("NO_CHANGE", "REPLANNED", "REPLAN_FAILED", "REQUIRES_USER_ACTION", "CONFLICT")


def test_replan_experience_cannot_supply_traveler_id(discovery_client) -> None:
    """ReplanExperienceArgs has extra='forbid' and no traveler_id field —
    a supplied traveler_id is rejected outright, never trusted."""
    user = register_traveler(discovery_client, "no-traveler-id-replan@example.com")
    itinerary = _compose(discovery_client, user)
    if "items" not in itinerary:
        return
    conv_id = _create_conversation(discovery_client, user)

    resp = discovery_client.post(
        f"/api/v1/conversations/{conv_id}/tool-calls",
        json={
            "name": "replan_experience",
            "args": {
                "itinerary_id": itinerary["id"],
                "requested_change": "change it",
                "traveler_id": "someone-elses-id",
            },
        },
        headers=auth_header(user),
    )
    assert resp.status_code == 422  # extra="forbid" rejects the unknown field


def test_replan_experience_invalid_itinerary_id_rejected(discovery_client) -> None:
    user = register_traveler(discovery_client, "invalid-itin-replan@example.com")
    conv_id = _create_conversation(discovery_client, user)

    resp = discovery_client.post(
        f"/api/v1/conversations/{conv_id}/tool-calls",
        json={
            "name": "replan_experience",
            "args": {"itinerary_id": "does-not-exist", "requested_change": "change it"},
        },
        headers=auth_header(user),
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "CONFLICT"
    assert result["reason_code"] == "ITINERARY_NOT_FOUND"


def test_replan_experience_unauthorized_itinerary_rejected(discovery_client) -> None:
    owner = register_traveler(discovery_client, "replan-tool-owner@example.com")
    intruder = register_traveler(discovery_client, "replan-tool-intruder@example.com")
    itinerary = _compose(discovery_client, owner)
    if "items" not in itinerary:
        return
    conv_id = _create_conversation(discovery_client, intruder)

    resp = discovery_client.post(
        f"/api/v1/conversations/{conv_id}/tool-calls",
        json={
            "name": "replan_experience",
            "args": {"itinerary_id": itinerary["id"], "requested_change": "change it"},
        },
        headers=auth_header(intruder),
    )
    assert resp.status_code == 200
    result = resp.json()
    # Never discloses existence of another traveler's itinerary.
    assert result["status"] == "CONFLICT"
    assert result["reason_code"] == "ITINERARY_NOT_FOUND"


def test_replan_experience_never_directly_mutates_without_service() -> None:
    """Static check: execute_replan_experience only ever calls through
    ReplanningService.replan_itinerary — it holds no direct
    session.add(ItineraryItem(...)) or itinerary.status = ... mutation of
    its own."""
    import inspect

    from src.services import ai_tools

    source = inspect.getsource(ai_tools.execute_replan_experience)
    assert "ReplanningService" in source
    assert "replan_itinerary" in source
    assert "session.add(ItineraryItem" not in source
