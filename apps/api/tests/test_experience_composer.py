"""ExperienceComposerService tests (Phase 8) — pure unit tests against
RankedExperienceItem fixtures (no DB), using MockRoutingAdapter for
deterministic travel times."""

from __future__ import annotations

import asyncio
from datetime import date, time

from src.adapters.routing import MockRoutingAdapter
from src.core.config import Settings
from src.schemas.experience import CategorySummary, LocationSummary, ProviderSummary
from src.schemas.ranking import RankedExperienceItem
from src.services.experience_composer import ExperienceComposerService

FORT_LAT, FORT_LNG = 18.9346, 72.8356


def _candidate(
    *,
    id_: str,
    rank: int,
    score: float,
    duration_minutes: int,
    price: float | None,
    lat: float = FORT_LAT,
    lng: float = FORT_LNG,
    category_slug: str = "food-drink",
) -> RankedExperienceItem:
    return RankedExperienceItem(
        id=id_,
        title=f"Experience {id_}",
        short_description="A test experience.",
        category=CategorySummary(id=f"cat-{category_slug}", slug=category_slug, name=category_slug.title()),
        location=LocationSummary(
            id=f"loc-{id_}", latitude=lat, longitude=lng, place_name=f"Place {id_}", address="addr", city="Mumbai"
        ),
        provider=ProviderSummary(
            id=f"prov-{id_}", business_name="Provider", verification_status="verified", is_synthetic=False
        ),
        currency="INR",
        price=price,
        price_type="fixed" if price is not None else "unknown",
        is_price_estimated=False,
        duration_minutes=duration_minutes,
        duration_is_estimated=False,
        status="active",
        verification_status="verified",
        is_synthetic=True,
        is_enriched=False,
        rank=rank,
        ranking_score=score,
        ranking_model_version="weighted-v1",
        semantic_relevance=score,
        personalized=False,
    )


def _settings() -> Settings:
    return Settings()


def test_basic_chronological_composition_no_overlap():
    candidates = [
        _candidate(id_="a", rank=1, score=0.9, duration_minutes=60, price=200),
        _candidate(id_="b", rank=2, score=0.8, duration_minutes=60, price=200),
    ]
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=5,
            max_budget=None,
            travel_mode="driving",
            origin_lat=FORT_LAT,
            origin_lng=FORT_LNG,
        )

    result = asyncio.run(_run())
    assert len(result.items) == 2
    items = sorted(result.items, key=lambda i: i.sequence_order)
    assert items[0].planned_end <= items[1].planned_start
    for i in range(len(items) - 1):
        assert items[i].planned_end <= items[i + 1].planned_start


def test_duration_too_long_excluded():
    candidates = [
        _candidate(id_="huge", rank=1, score=0.99, duration_minutes=600, price=100),
        _candidate(id_="fits", rank=2, score=0.5, duration_minutes=60, price=100),
    ]
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(11, 0),  # only 2h window
            max_experiences=5,
            max_budget=None,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
        )

    result = asyncio.run(_run())
    ids = {i.experience.id for i in result.items}
    assert "huge" not in ids
    assert "fits" in ids


def test_budget_ceiling_respected():
    candidates = [
        _candidate(id_="expensive", rank=1, score=0.9, duration_minutes=30, price=5000),
        _candidate(id_="cheap", rank=2, score=0.8, duration_minutes=30, price=100),
    ]
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=5,
            max_budget=500,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
        )

    result = asyncio.run(_run())
    ids = {i.experience.id for i in result.items}
    assert "expensive" not in ids
    assert "cheap" in ids
    assert result.estimated_total_cost <= 500


def test_over_budget_all_candidates_rejected_empty_result():
    candidates = [_candidate(id_="a", rank=1, score=0.9, duration_minutes=30, price=99999)]
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=5,
            max_budget=10,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
        )

    result = asyncio.run(_run())
    assert result.items == []


def test_higher_ranking_score_preferred_when_constraints_equal():
    candidates = [
        _candidate(id_="low", rank=2, score=0.5, duration_minutes=30, price=100),
        _candidate(id_="high", rank=1, score=0.95, duration_minutes=30, price=100),
    ]
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(10, 0),  # tight window: only 1 fits well
            max_experiences=1,
            max_budget=None,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
        )

    result = asyncio.run(_run())
    assert len(result.items) == 1
    assert result.items[0].experience.id == "high"


def test_determinism_same_inputs_identical_output():
    candidates = [
        _candidate(id_="a", rank=1, score=0.9, duration_minutes=60, price=200),
        _candidate(id_="b", rank=2, score=0.8, duration_minutes=60, price=200),
        _candidate(id_="c", rank=3, score=0.7, duration_minutes=60, price=200),
    ]

    async def _run():
        composer = ExperienceComposerService(_settings(), MockRoutingAdapter())
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=5,
            max_budget=None,
            travel_mode="driving",
            origin_lat=FORT_LAT,
            origin_lng=FORT_LNG,
        )

    result_a = asyncio.run(_run())
    result_b = asyncio.run(_run())
    ids_a = [i.experience.id for i in result_a.items]
    ids_b = [i.experience.id for i in result_b.items]
    assert ids_a == ids_b


def test_empty_candidates_never_fabricates_item():
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=[],
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=5,
            max_budget=None,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
        )

    result = asyncio.run(_run())
    assert result.items == []


def test_pace_changes_buffer_between_selected_stops():
    candidates = [
        _candidate(id_="a", rank=1, score=0.9, duration_minutes=30, price=100),
        _candidate(id_="b", rank=2, score=0.8, duration_minutes=30, price=100),
    ]

    async def _run(pace: str):
        return await ExperienceComposerService(_settings(), MockRoutingAdapter()).compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=2,
            max_budget=None,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
            pace=pace,
        )

    relaxed = asyncio.run(_run("relaxed"))
    balanced = asyncio.run(_run("balanced"))
    packed = asyncio.run(_run("packed"))
    assert relaxed.items[1].buffer_before_minutes > balanced.items[1].buffer_before_minutes
    assert packed.items[1].buffer_before_minutes < balanced.items[1].buffer_before_minutes


def test_category_diversity_preference_when_quality_equal():
    """When two candidates tie on rank/score, composer should still
    produce a deterministic, valid composition (no crash / no forced
    duplicate) — diversity is a soft tie-break in stage B, not a hard
    requirement, so this asserts determinism + validity rather than an
    exact category set."""
    candidates = [
        _candidate(id_="a", rank=1, score=0.8, duration_minutes=30, price=100, category_slug="food-drink"),
        _candidate(id_="b", rank=2, score=0.8, duration_minutes=30, price=100, category_slug="culture-heritage"),
    ]
    composer = ExperienceComposerService(_settings(), MockRoutingAdapter())

    async def _run():
        return await composer.compose(
            candidates=candidates,
            itinerary_date=date(2026, 10, 12),
            start_time_of_day=time(9, 0),
            end_time_of_day=time(18, 0),
            max_experiences=2,
            max_budget=None,
            travel_mode="driving",
            origin_lat=None,
            origin_lng=None,
        )

    result = asyncio.run(_run())
    assert len(result.items) == 2
    categories = {i.experience.category.slug for i in result.items}
    assert len(categories) == 2
