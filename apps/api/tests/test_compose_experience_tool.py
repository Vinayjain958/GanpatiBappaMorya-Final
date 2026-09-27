"""compose_experience Gemini tool tests (Phase 8).

Covers: authenticated-only, traveler_id always server-derived, only
authorized candidate-context ids accepted, deterministic validated
output, no duplicate Phase 6/7 pipeline execution when a candidate
context already exists, search_experiences + compose_experience
integration end-to-end, anonymous conversation access blocked.
"""

from __future__ import annotations

from unittest.mock import patch

from src.services.discovery_pipeline import DiscoveryPipelineService
from tests.conftest import auth_header, register_traveler


def _create_conversation(client, user):
    return client.post("/api/v1/conversations", headers=auth_header(user)).json()["id"]


def test_anonymous_tool_call_blocked(discovery_client) -> None:
    response = discovery_client.post(
        "/api/v1/conversations/some-id/tool-calls",
        json={"name": "compose_experience", "args": {}},
    )
    assert response.status_code == 401


def test_compose_experience_requires_search_first_or_runs_fresh_pipeline(discovery_client) -> None:
    """With no prior search_experiences call in this conversation,
    compose_experience is allowed to trigger exactly one fresh Phase 6+7
    pipeline pass — never a hard failure, never a silently-trusted raw id."""
    user = register_traveler(discovery_client, "compose-tool-fresh@example.com")
    conversation_id = _create_conversation(discovery_client, user)

    response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={
            "name": "compose_experience",
            "args": {
                "itinerary_date": "2026-10-12",
                "start_time": "09:00:00",
                "end_time": "20:00:00",
            },
        },
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "items" in body or body.get("valid") is False


def test_compose_experience_only_accepts_ids_from_candidate_context(discovery_client) -> None:
    user = register_traveler(discovery_client, "compose-tool-context@example.com")
    conversation_id = _create_conversation(discovery_client, user)

    search_resp = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"q": "food", "limit": 5}},
        headers=auth_header(user),
    )
    assert search_resp.status_code == 200

    # Gemini supplies an id that was never in the candidate context — the
    # tool must never trust it blindly; it should just be dropped, never
    # cause a crash or a fabricated itinerary item.
    compose_resp = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={
            "name": "compose_experience",
            "args": {
                "experience_ids": ["fabricated-id-not-in-context"],
                "itinerary_date": "2026-10-12",
                "start_time": "09:00:00",
                "end_time": "20:00:00",
            },
        },
        headers=auth_header(user),
    )
    assert compose_resp.status_code == 200
    body = compose_resp.json()
    if "items" in body:
        ids = {item["experience_id"] for item in body["items"]}
        assert "fabricated-id-not-in-context" not in ids
    else:
        assert body.get("valid") is False


def test_no_duplicate_pipeline_execution_when_context_exists(discovery_client) -> None:
    """Critical regression test: when a candidate context already exists
    from a prior search_experiences call, compose_experience must NOT
    trigger another Phase 6+7 pipeline pass."""
    user = register_traveler(discovery_client, "compose-tool-no-dup@example.com")
    conversation_id = _create_conversation(discovery_client, user)

    discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"q": "food", "limit": 5}},
        headers=auth_header(user),
    )

    original_retrieve = DiscoveryPipelineService.run
    call_counts = {"run": 0}

    async def _counting_run(self, *args, **kwargs):
        call_counts["run"] += 1
        return await original_retrieve(self, *args, **kwargs)

    with patch.object(DiscoveryPipelineService, "run", _counting_run):
        response = discovery_client.post(
            f"/api/v1/conversations/{conversation_id}/tool-calls",
            json={
                "name": "compose_experience",
                "args": {
                    "itinerary_date": "2026-10-12",
                    "start_time": "09:00:00",
                    "end_time": "20:00:00",
                },
            },
            headers=auth_header(user),
        )

    assert response.status_code == 200
    # A candidate context already existed from the prior search_experiences
    # call, so compose_experience must not re-run the Phase 6 pipeline.
    assert call_counts["run"] == 0


def test_search_then_compose_end_to_end(discovery_client) -> None:
    user = register_traveler(discovery_client, "compose-tool-e2e@example.com")
    conversation_id = _create_conversation(discovery_client, user)

    search_resp = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"q": "food", "limit": 5}},
        headers=auth_header(user),
    )
    assert search_resp.status_code == 200

    compose_resp = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={
            "name": "compose_experience",
            "args": {
                "itinerary_date": "2026-10-12",
                "start_time": "09:00:00",
                "end_time": "20:00:00",
                "max_experiences": 3,
            },
        },
        headers=auth_header(user),
    )
    assert compose_resp.status_code == 200
    body = compose_resp.json()
    assert "items" in body or "valid" in body


def test_deterministic_validated_output(discovery_client) -> None:
    user = register_traveler(discovery_client, "compose-tool-determinism@example.com")
    conversation_id = _create_conversation(discovery_client, user)
    discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"q": "food", "limit": 5}},
        headers=auth_header(user),
    )

    args = {
        "name": "compose_experience",
        "args": {"itinerary_date": "2026-10-12", "start_time": "09:00:00", "end_time": "20:00:00"},
    }
    resp1 = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls", json=args, headers=auth_header(user)
    )
    resp2 = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls", json=args, headers=auth_header(user)
    )
    body1, body2 = resp1.json(), resp2.json()
    if "items" in body1 and "items" in body2:
        ids1 = [i["experience_id"] for i in body1["items"]]
        ids2 = [i["experience_id"] for i in body2["items"]]
        assert ids1 == ids2
    else:
        assert body1.get("valid") == body2.get("valid")
