from __future__ import annotations

from tests.conftest import auth_header, register_traveler


def test_create_conversation_requires_auth(discovery_client) -> None:
    response = discovery_client.post("/api/v1/conversations")
    assert response.status_code == 401


def test_create_conversation_scoped_to_user(discovery_client) -> None:
    user = register_traveler(discovery_client, "voice-traveler@example.com")
    response = discovery_client.post("/api/v1/conversations", headers=auth_header(user))
    assert response.status_code == 201
    body = response.json()
    assert "id" in body and "created_at" in body


def test_messages_route_404s_for_another_users_conversation(discovery_client) -> None:
    owner = register_traveler(discovery_client, "owner@example.com")
    other = register_traveler(discovery_client, "intruder@example.com")

    created = discovery_client.post("/api/v1/conversations", headers=auth_header(owner)).json()
    conversation_id = created["id"]

    response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "hello"},
        headers=auth_header(other),
    )
    assert response.status_code == 404


def test_get_conversation_404s_for_another_users_conversation(discovery_client) -> None:
    owner = register_traveler(discovery_client, "owner2@example.com")
    other = register_traveler(discovery_client, "intruder2@example.com")

    created = discovery_client.post("/api/v1/conversations", headers=auth_header(owner)).json()
    conversation_id = created["id"]

    response = discovery_client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_header(other))
    assert response.status_code == 404


def test_text_turn_happy_path_returns_results(discovery_client) -> None:
    user = register_traveler(discovery_client, "happy-path@example.com")
    created = discovery_client.post("/api/v1/conversations", headers=auth_header(user)).json()
    conversation_id = created["id"]

    response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "I want cheap local food near Fort"},
        headers=auth_header(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_text"]
    assert body["traveler_context"]["raw_query"] == "I want cheap local food near Fort"
    assert body["tool_results"] is not None


def test_get_conversation_returns_bounded_history(discovery_client) -> None:
    user = register_traveler(discovery_client, "history@example.com")
    created = discovery_client.post("/api/v1/conversations", headers=auth_header(user)).json()
    conversation_id = created["id"]

    discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "food near Fort"},
        headers=auth_header(user),
    )

    response = discovery_client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_header(user))
    assert response.status_code == 200
    body = response.json()
    assert len(body["messages"]) == 2  # user + assistant
    assert body["latest_traveler_context"] is not None


def test_tool_call_rejects_unknown_tool(discovery_client) -> None:
    user = register_traveler(discovery_client, "tool-unknown@example.com")
    created = discovery_client.post("/api/v1/conversations", headers=auth_header(user)).json()
    conversation_id = created["id"]

    response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "delete_database", "args": {}},
        headers=auth_header(user),
    )
    assert response.status_code == 422


def test_tool_call_rejects_malformed_args(discovery_client) -> None:
    user = register_traveler(discovery_client, "tool-malformed@example.com")
    created = discovery_client.post("/api/v1/conversations", headers=auth_header(user)).json()
    conversation_id = created["id"]

    response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"limit": "not-a-number"}},
        headers=auth_header(user),
    )
    assert response.status_code == 422


def test_tool_call_happy_path_returns_capped_results_and_persists_message(discovery_client) -> None:
    user = register_traveler(discovery_client, "tool-happy@example.com")
    created = discovery_client.post("/api/v1/conversations", headers=auth_header(user)).json()
    conversation_id = created["id"]

    response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"q": "food", "limit": 2}},
        headers=auth_header(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 2

    detail = discovery_client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_header(user)).json()
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["role"] == "assistant"


def test_tool_call_search_experiences_with_stored_budget_context_does_not_crash(discovery_client) -> None:
    """Regression test: conversation.latest_traveler_context is stored as
    a raw JSON dict, and was previously passed unvalidated into the
    ranking pipeline, which attribute-accesses context.budget_max —
    raising AttributeError the moment a conversation had a budget-bearing
    context on record. A prior text turn sets latest_traveler_context
    with a real budget; the tool call must not crash."""
    user = register_traveler(discovery_client, "tool-budget-context@example.com")
    created = discovery_client.post("/api/v1/conversations", headers=auth_header(user)).json()
    conversation_id = created["id"]

    text_response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "I want food under 1000 rupees"},
        headers=auth_header(user),
    )
    assert text_response.status_code == 200

    tool_response = discovery_client.post(
        f"/api/v1/conversations/{conversation_id}/tool-calls",
        json={"name": "search_experiences", "args": {"q": "food", "limit": 2}},
        headers=auth_header(user),
    )
    assert tool_response.status_code == 200
