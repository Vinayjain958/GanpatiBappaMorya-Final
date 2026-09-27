"""Deterministic image-matching/scoring tests for
src/services/experience_images.py — no network, no LLM. Covers exact
name matching, rejection of unrelated images despite a text-search hit,
geographic scoring, semantic fallback, and the full resolution ladder
against a fake adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from src.adapters.wikimedia_commons import WikimediaImage
from src.core.config import Settings
from src.services.experience_images import (
    name_similarity,
    normalize_name,
    resolve_experience_image,
    score_geosearch_match,
    score_semantic_match,
    score_title_match,
)


def _image(**overrides) -> WikimediaImage:
    defaults = dict(
        title="File:Example.jpg",
        page_id=1,
        image_url="https://upload.wikimedia.org/example.jpg",
        thumbnail_url="https://thumb.wikimedia.org/example_thumb.jpg",
        description_url="https://commons.wikimedia.org/wiki/File:Example.jpg",
        width=1600,
        height=1200,
        license="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0",
        author="Jane Doe",
        attribution_required=True,
        categories=[],
        latitude=None,
        longitude=None,
        distance_km=None,
    )
    defaults.update(overrides)
    return WikimediaImage(**defaults)


# ─── Name normalization / similarity ────────────────────────────────────────


def test_normalize_name_strips_punctuation_and_case() -> None:
    assert normalize_name("Timezone R City Mall Ghatkopar - Arcade Games, VR & Prizes") == (
        "timezone r city mall ghatkopar arcade games vr prizes"
    )


def test_exact_normalized_match_scores_one() -> None:
    assert name_similarity("KidZania Mumbai", "kidzania mumbai") == 1.0


def test_single_shared_brand_word_across_different_branches_scores_zero() -> None:
    # Real false positive found in live testing: an unrelated overseas
    # "Timezone" branch must not match on the brand word alone.
    score = name_similarity(
        "File:Timezone Christchurch Central.png Timezone",
        "Timezone R City Mall Ghatkopar - Arcade Games, VR & Prizes",
    )
    assert score == 0.0


def test_single_shared_surname_scores_zero() -> None:
    # Real false positive found in live testing: an unrelated person's
    # photo must not match a venue on a shared surname token alone.
    score = name_similarity("File:Ajmera Babi.jpg Ajmera", "Ajmera IndiKarting")
    assert score == 0.0


def test_unrelated_names_score_zero() -> None:
    # The task's canonical counter-example: an arcade must not match a
    # surf-beach photo just because both are loosely "adventure".
    score = name_similarity(
        "Timezone R City Mall Ghatkopar – Arcade Games, VR & Prizes", "Surfer at Goa Beach"
    )
    assert score == 0.0


def test_full_containment_of_shorter_name_scores_as_strong_match() -> None:
    # "Timezone R City Mall" is entirely contained in the longer official
    # title — a real match, not merely "partial" (containment scoring).
    score = name_similarity(
        "Timezone R City Mall Ghatkopar – Arcade Games, VR & Prizes", "Timezone R City Mall"
    )
    assert score == 1.0


def test_single_word_candidate_name_never_matches_alone() -> None:
    # A single-word provider/experience name (e.g. a common brand word)
    # must never be treated as sufficient evidence on its own, even for
    # an exact single-token match — this is what let "Timezone" and
    # "Ajmera" false-positive against unrelated files in live testing.
    assert name_similarity("File:Timezone Christchurch Central.png Timezone", "Timezone") == 0.0
    assert name_similarity("Timezone", "Timezone") == 1.0  # exact identical strings still short-circuit


def test_loose_word_overlap_scores_between_zero_and_one() -> None:
    # Some shared tokens but neither name contains the other -> partial.
    score = name_similarity("Timezone R City Mall Ghatkopar Arcade", "R City Mall Food Court")
    assert 0.0 < score < 1.0


# ─── Title-search scoring ───────────────────────────────────────────────────


def test_strong_title_match_scores_high() -> None:
    image = _image(title="File:KidZania Mumbai entrance.jpg", categories=["KidZania"])
    score = score_title_match(image, ["KidZania Mumbai"])
    assert score >= 80.0


def test_scattered_word_order_does_not_reach_strong_tier() -> None:
    # Real false positive found in live testing: "Polo World Cup ... on
    # Snow" contains both words "snow" and "world" (just reordered and
    # apart) but is not a photo of an actual "Snow World" venue — must
    # not reach the same strong tier as a genuine "Snow World" photo.
    scattered = _image(
        title="File:30th St. Moritz Polo World Cup on Snow - Cartier vs Ralph Lauren.jpg",
        categories=["Self-published work"],
    )
    genuine = _image(title="File:Photo from Snow world Hyderabad 3971.jpg", categories=["Snow World Hyderabad"])

    scattered_score = score_title_match(scattered, ["Snow World"])
    genuine_score = score_title_match(genuine, ["Snow World"])

    assert genuine_score == 80.0
    assert scattered_score < genuine_score


def test_unrelated_title_search_hit_rejected_despite_matching_search() -> None:
    # Mirrors the real KidZania Commons account uploading unrelated stock
    # photos ("Natural Disaster06.jpg") tagged with the same author/user —
    # a text search can surface it, but title/category relevance must not.
    image = _image(title="File:Natural Disaster06.jpg", categories=["Disasters"])
    score = score_title_match(image, ["KidZania Mumbai"])
    assert score < 0


# ─── Geosearch scoring ───────────────────────────────────────────────────────


def test_geosearch_close_with_name_match_scores_as_strong() -> None:
    image = _image(title="File:R City Mall exterior.jpg", categories=["R City Mall"], distance_km=0.1)
    score = score_geosearch_match(image, ["Timezone R City Mall Ghatkopar"], radius_km=1.0)
    assert score >= 60.0


def test_geosearch_far_unrelated_church_scores_low() -> None:
    # The task's canonical counter-example: a random church 3.8km away
    # must not outrank a genuinely relevant nearby image.
    image = _image(title="File:Random Church.jpg", categories=["Churches"], distance_km=3.8)
    score = score_geosearch_match(image, ["Timezone R City Mall Ghatkopar"], radius_km=5.0)
    assert score < 20.0


def test_geosearch_proximity_only_scores_lower_than_name_plus_proximity() -> None:
    close_no_name = _image(title="File:Unnamed street.jpg", distance_km=0.2)
    close_with_name = _image(title="File:R City Mall street.jpg", categories=["R City Mall"], distance_km=0.2)

    score_no_name = score_geosearch_match(close_no_name, ["R City Mall"], radius_km=1.0)
    score_with_name = score_geosearch_match(close_with_name, ["R City Mall"], radius_km=1.0)

    assert score_with_name > score_no_name


# ─── Semantic fallback scoring ───────────────────────────────────────────────


def test_semantic_fallback_scores_below_place_specific_threshold() -> None:
    image = _image(title="File:Generic arcade.jpg", width=1600, height=1200)
    score = score_semantic_match(image, ["arcade games"])
    assert 0 < score < 60.0  # never reaches "place-specific" tier


# ─── Full resolution ladder (fake adapter) ──────────────────────────────────


class _FakeAdapter:
    def __init__(self, *, title_results=None, geo_results=None, exact_file=None):
        self._title_results = title_results or {}
        self._geo_results = geo_results or {}
        self._exact_file = exact_file
        self.title_calls: list[str] = []
        self.geo_calls: list[tuple[float, float, int]] = []

    async def search_by_title(self, query, *, limit):
        self.title_calls.append(query)
        return self._title_results.get(query, [])

    async def search_nearby(self, lat, lng, radius_m, *, limit):
        self.geo_calls.append((lat, lng, radius_m))
        return self._geo_results.get(radius_m, [])

    async def resolve_file(self, title):
        return self._exact_file if self._exact_file and self._exact_file.title == title else None


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_resolution_prefers_exact_title_match_over_geosearch() -> None:
    exact = _image(title="File:KidZania Mumbai.jpg", categories=["KidZania"])
    nearby = _image(title="File:Random Church.jpg", distance_km=0.5)
    adapter = _FakeAdapter(
        title_results={"KidZania Mumbai": [exact]},
        geo_results={1000: [nearby]},
    )

    result = asyncio.run(
        resolve_experience_image(
            experience_title="KidZania Mumbai",
            provider_name="KidZania",
            location_name=None,
            category_slug="entertainment",
            latitude=19.08,
            longitude=72.88,
            known_commons_file=None,
            adapter=adapter,
            settings=_settings(),
        )
    )

    assert result is not None
    assert result.matched_by == "exact_title"
    assert result.is_place_specific is True
    assert result.is_synthetic is False
    # High-confidence exact match short-circuits — no geosearch needed.
    assert adapter.geo_calls == []


def test_resolution_falls_through_to_semantic_when_nothing_relevant() -> None:
    unrelated_title_hit = _image(title="File:Natural Disaster06.jpg", categories=["Disasters"])
    unrelated_geo_hit = _image(title="File:Random Church.jpg", distance_km=4.9)
    semantic_hit = _image(title="File:Arcade games generic.jpg", categories=["Arcade games"])

    adapter = _FakeAdapter(
        title_results={
            "Timezone Arcade": [unrelated_title_hit],
            "arcade games": [semantic_hit],
        },
        geo_results={1000: [], 3000: [], 5000: [unrelated_geo_hit]},
    )

    result = asyncio.run(
        resolve_experience_image(
            experience_title="Timezone Arcade",
            provider_name="Timezone",
            location_name=None,
            category_slug="entertainment",
            latitude=19.08,
            longitude=72.88,
            known_commons_file=None,
            adapter=adapter,
            settings=_settings(wikimedia_min_match_score=20.0),
        )
    )

    assert result is not None
    assert result.matched_by == "semantic_fallback"
    assert result.is_place_specific is False
    assert result.is_synthetic is False


def test_resolution_returns_none_when_nothing_clears_threshold() -> None:
    unrelated = _image(title="File:Natural Disaster06.jpg", categories=["Disasters"])
    adapter = _FakeAdapter(title_results={"Obscure Venue": [unrelated]}, geo_results={})

    result = asyncio.run(
        resolve_experience_image(
            experience_title="Obscure Venue",
            provider_name="Obscure Venue",
            location_name=None,
            category_slug="hidden-gems",  # no semantic terms configured -> nothing to fall back on
            latitude=19.08,
            longitude=72.88,
            known_commons_file=None,
            adapter=adapter,
            settings=_settings(),
        )
    )

    # hidden-gems has semantic terms configured but adapter returns
    # nothing for them (not stubbed) -> falls through to None.
    assert result is None


def test_resolution_uses_exact_commons_link_when_available() -> None:
    linked = _image(title="File:Linked Reference.jpg", categories=["Linked"])
    adapter = _FakeAdapter(exact_file=linked)

    result = asyncio.run(
        resolve_experience_image(
            experience_title="Some Venue",
            provider_name="Some Venue",
            location_name=None,
            category_slug="museums",
            latitude=19.08,
            longitude=72.88,
            known_commons_file="File:Linked Reference.jpg",
            adapter=adapter,
            settings=_settings(),
        )
    )

    assert result is not None
    assert result.matched_by == "exact_commons_link"
    assert result.match_score == 100.0


def test_resolution_never_marks_wikimedia_result_as_synthetic() -> None:
    exact = _image(title="File:Grand Heritage Museum.jpg", categories=["Grand Heritage Museum"])
    adapter = _FakeAdapter(title_results={"Grand Heritage Museum": [exact]})

    result = asyncio.run(
        resolve_experience_image(
            experience_title="Grand Heritage Museum",
            provider_name="Grand Heritage Museum",
            location_name=None,
            category_slug="museums",
            latitude=19.08,
            longitude=72.88,
            known_commons_file=None,
            adapter=adapter,
            settings=_settings(),
        )
    )

    assert result is not None
    assert result.is_synthetic is False


def test_attribution_text_includes_author_and_license() -> None:
    exact = _image(
        title="File:Grand Heritage Museum.jpg",
        categories=["Grand Heritage Museum"],
        author="Jane Doe",
        license="CC BY-SA 4.0",
    )
    adapter = _FakeAdapter(title_results={"Grand Heritage Museum": [exact]})

    result = asyncio.run(
        resolve_experience_image(
            experience_title="Grand Heritage Museum",
            provider_name="Grand Heritage Museum",
            location_name=None,
            category_slug="museums",
            latitude=19.08,
            longitude=72.88,
            known_commons_file=None,
            adapter=adapter,
            settings=_settings(),
        )
    )

    assert result is not None
    assert "Jane Doe" in result.attribution_text
    assert "CC BY-SA 4.0" in result.attribution_text
