"""MockEmbeddingAdapter tests (Phase 6) — deterministic, not random;
fixed dimensionality; asymmetric query/document distinction in the text
fed to the vector, not just cosmetic."""

from __future__ import annotations

import asyncio

from src.adapters.embedding import MockEmbeddingAdapter
from src.core.vector_math import cosine_similarity


def test_mock_adapter_is_deterministic():
    adapter = MockEmbeddingAdapter(dimensions=128)
    v1 = asyncio.run(adapter.embed_query("street food near Fort"))
    v2 = asyncio.run(adapter.embed_query("street food near Fort"))
    assert v1 == v2


def test_mock_adapter_respects_configured_dimensions():
    adapter = MockEmbeddingAdapter(dimensions=256)
    v = asyncio.run(adapter.embed_query("test"))
    assert len(v) == 256


def test_mock_adapter_similar_text_more_similar_than_unrelated():
    adapter = MockEmbeddingAdapter(dimensions=256)
    a = asyncio.run(adapter.embed_document("Street Food Tour", "Explore street food stalls near Fort"))
    b = asyncio.run(adapter.embed_document("Food Walking Tour", "Sample street food near Fort market"))
    c = asyncio.run(adapter.embed_document("Scuba Diving Course", "Learn to scuba dive in open water"))

    sim_ab = cosine_similarity(a, b)
    sim_ac = cosine_similarity(a, c)
    assert sim_ab > sim_ac


def test_mock_adapter_batch_matches_individual_calls():
    adapter = MockEmbeddingAdapter(dimensions=128)
    docs = [("Title A", "Text A"), ("Title B", "Text B")]
    batch = asyncio.run(adapter.embed_documents(docs))
    individual = [asyncio.run(adapter.embed_document(t, x)) for t, x in docs]
    assert batch == individual


def test_mock_adapter_empty_text_returns_stable_nonzero_vector():
    adapter = MockEmbeddingAdapter(dimensions=64)
    v = asyncio.run(adapter.embed_query(""))
    assert len(v) == 64
    assert any(x != 0.0 for x in v)
