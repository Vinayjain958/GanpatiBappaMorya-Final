"""Cosine similarity consistency test (Phase 6) — SQLite Python impl
produces the expected ordering vs hand-computed values."""

from __future__ import annotations

import math

import pytest

from src.core.vector_math import cosine_similarity


def test_identical_vectors_similarity_is_one():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_orthogonal_vectors_similarity_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_opposite_vectors_similarity_is_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_hand_computed_value():
    a = [1.0, 2.0]
    b = [2.0, 1.0]
    expected = (1 * 2 + 2 * 1) / (math.sqrt(1 + 4) * math.sqrt(4 + 1))
    assert cosine_similarity(a, b) == pytest.approx(expected)


def test_zero_vector_similarity_is_zero_not_nan():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_ordering_matches_hand_computed_ranking():
    query = [1.0, 0.0, 0.0]
    docs = {
        "close": [0.9, 0.1, 0.0],
        "medium": [0.5, 0.5, 0.0],
        "far": [0.0, 1.0, 0.0],
    }
    scored = {name: cosine_similarity(query, vec) for name, vec in docs.items()}
    ranking = sorted(scored, key=lambda k: scored[k], reverse=True)
    assert ranking == ["close", "medium", "far"]


def test_mismatched_length_raises():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0])
