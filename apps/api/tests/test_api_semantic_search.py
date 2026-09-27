"""API tests for POST /api/v1/experiences/semantic-search and
POST /api/v1/feasibility/check (Phase 6). Uses the shared `client` fixture
(MockAIAdapter/MockEmbeddingAdapter/Mock location adapters, seeded with
one experience via `seeded_ids`)."""

from __future__ import annotations

from tests.conftest import auth_header, register_traveler


def test_semantic_search_requires_auth(client):
    response = client.post("/api/v1/experiences/semantic-search", json={"query": "food"})
    assert response.status_code == 401


def test_semantic_search_returns_only_feasible_items(client):
    user = register_traveler(client, "semsearch@example.com")
    response = client.post(
        "/api/v1/experiences/semantic-search",
        json={"query": "test experience", "limit": 5},
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "items" in body
    assert body["retrieval_mode"] in ("sqlite_python_semantic", "keyword_fallback", "pgvector_semantic")
    assert "excluded_summary" in body
    assert isinstance(body["candidate_count"], int)


def test_semantic_search_budget_excludes_over_budget_item(client, seeded_ids):
    user = register_traveler(client, "budgetsearch@example.com")
    response = client.post(
        "/api/v1/experiences/semantic-search",
        json={"query": "test", "constraints": {"budget_max": 1}},
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Seeded experience has min/max price 100-500 -> excluded at budget_max=1.
    assert body["feasible_count"] == 0


def test_feasibility_check_requires_auth(client, seeded_ids):
    response = client.post(
        "/api/v1/feasibility/check", json={"experience_id": seeded_ids["experience_id"]}
    )
    assert response.status_code == 401


def test_feasibility_check_returns_verdict(client, seeded_ids):
    user = register_traveler(client, "feascheck@example.com")
    response = client.post(
        "/api/v1/feasibility/check",
        json={"experience_id": seeded_ids["experience_id"], "constraints": {"budget_max": 1000}},
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["experience_id"] == seeded_ids["experience_id"]
    assert body["status"] in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")


def test_feasibility_check_unknown_experience_404(client):
    user = register_traveler(client, "feas404@example.com")
    response = client.post(
        "/api/v1/feasibility/check",
        json={"experience_id": "does-not-exist"},
        headers=auth_header(user),
    )
    assert response.status_code == 404


def test_feasibility_check_negative_budget_rejected(client, seeded_ids):
    user = register_traveler(client, "feasneg@example.com")
    response = client.post(
        "/api/v1/feasibility/check",
        json={"experience_id": seeded_ids["experience_id"], "constraints": {"budget_max": -50}},
        headers=auth_header(user),
    )
    assert response.status_code == 422
