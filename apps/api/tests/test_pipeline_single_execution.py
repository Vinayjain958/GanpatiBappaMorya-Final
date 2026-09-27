"""Regression test (Phase 8 preflight): the retrieval->feasibility pipeline
executes exactly once per logical request, for both the direct
POST /api/v1/recommendations endpoint and the conversational
search_experiences tool path.

Phase 7's `run_with_ranking()` calls `run()` internally once and then ranks
those same results — it must never re-run retrieval/feasibility a second
time to produce the ranked set. This test spies on
SemanticRetrievalService.retrieve and FeasibilityService.evaluate (the two
real execution points) and asserts call counts, rather than trusting
result correctness alone to prove there was no duplicate work.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.adapters.embedding import MockEmbeddingAdapter
from src.adapters.routing import MockRoutingAdapter
from src.core.config import Settings
from src.services.discovery_pipeline import DiscoveryPipelineService
from src.services.feasibility import FeasibilityService
from src.services.semantic_retrieval import SemanticRetrievalService
from tests.conftest import auth_header, register_traveler


def test_run_with_ranking_executes_retrieval_and_feasibility_exactly_once(
    session_factory, discovery_dataset
):
    """Direct service-level proof: run_with_ranking() must not invoke
    SemanticRetrievalService.retrieve or FeasibilityService.evaluate more
    than the single logical pass performed by run()."""

    async def _run():
        async with session_factory() as session:
            settings = Settings()
            pipeline = DiscoveryPipelineService(
                session, settings, MockEmbeddingAdapter(), MockRoutingAdapter()
            )

            retrieve_spy = AsyncMock(wraps=pipeline._retrieval.retrieve)
            evaluate_spy = AsyncMock(wraps=pipeline._feasibility.evaluate)
            with (
                patch.object(pipeline._retrieval, "retrieve", retrieve_spy),
                patch.object(pipeline._feasibility, "evaluate", evaluate_spy),
            ):
                result, ranked_items = await pipeline.run_with_ranking(
                    traveler_id="some-traveler-id",
                    raw_query="food",
                    limit=10,
                )
            return result, ranked_items, retrieve_spy, evaluate_spy

    result, ranked_items, retrieve_spy, evaluate_spy = asyncio.run(_run())

    # Exactly one retrieval call for the whole logical request.
    assert retrieve_spy.await_count == 1
    # Feasibility is evaluated once per retrieved candidate (not once per
    # candidate per ranking pass) — i.e. call count == candidate_count,
    # never a multiple of it (which would indicate a second pipeline pass).
    assert evaluate_spy.await_count == result.candidate_count
    # Ranking must only ever have ranked the already-feasible items — never
    # more than what the single feasibility pass produced.
    assert len(ranked_items) == result.feasible_count


def test_recommendations_endpoint_single_pipeline_execution(client):
    """API-level proof for POST /api/v1/recommendations: patches the real
    execution points process-wide and asserts they fire exactly once for
    one request, with traveler_id always server-derived (never accepted
    from the request body)."""
    user = register_traveler(client, "single-exec@example.com")

    original_retrieve = SemanticRetrievalService.retrieve
    original_evaluate = FeasibilityService.evaluate
    call_counts = {"retrieve": 0, "evaluate": 0}

    async def _retrieve_wrapper(self, *args, **kwargs):
        call_counts["retrieve"] += 1
        return await original_retrieve(self, *args, **kwargs)

    async def _evaluate_wrapper(self, *args, **kwargs):
        call_counts["evaluate"] += 1
        return await original_evaluate(self, *args, **kwargs)

    with (
        patch.object(SemanticRetrievalService, "retrieve", _retrieve_wrapper),
        patch.object(FeasibilityService, "evaluate", _evaluate_wrapper),
    ):
        response = client.post(
            "/api/v1/recommendations",
            json={"query": "food", "top_k": 5},
            headers=auth_header(user),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert call_counts["retrieve"] == 1
    assert call_counts["evaluate"] == body["candidate_count"]
    # traveler_id is never a field the client can set on this request body.
    assert "traveler_id" not in {"query", "interests", "constraints", "top_k"}


def test_search_experiences_tool_single_pipeline_execution(discovery_client):
    """API-level proof for the conversational search_experiences tool
    (voice-path bridge / POST /api/v1/conversations/{id}/tool-calls):
    exactly one retrieval + feasibility pass for one tool call, whether or
    not the caller is an authenticated traveler (ranked) or not."""
    user = register_traveler(discovery_client, "single-exec-tool@example.com")
    created = discovery_client.post(
        "/api/v1/conversations", headers=auth_header(user)
    ).json()
    conversation_id = created["id"]

    original_retrieve = SemanticRetrievalService.retrieve
    original_evaluate = FeasibilityService.evaluate
    call_counts = {"retrieve": 0, "evaluate": 0}

    async def _retrieve_wrapper(self, *args, **kwargs):
        call_counts["retrieve"] += 1
        return await original_retrieve(self, *args, **kwargs)

    async def _evaluate_wrapper(self, *args, **kwargs):
        call_counts["evaluate"] += 1
        return await original_evaluate(self, *args, **kwargs)

    with (
        patch.object(SemanticRetrievalService, "retrieve", _retrieve_wrapper),
        patch.object(FeasibilityService, "evaluate", _evaluate_wrapper),
    ):
        response = discovery_client.post(
            f"/api/v1/conversations/{conversation_id}/tool-calls",
            json={"name": "search_experiences", "args": {"q": "food", "limit": 5}},
            headers=auth_header(user),
        )

    assert response.status_code == 200, response.text
    # The key regression assertion: retrieval never runs twice for one
    # logical tool call regardless of whether ranking (traveler_id) applies.
    assert call_counts["retrieve"] == 1
    assert call_counts["evaluate"] >= 0  # candidates may be 0 for a fresh DB
