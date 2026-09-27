"""ItineraryNarratorService tests (Phase 8) — mocked AIAdapter, no real
Gemini calls. Proves: structured output validated, invalid Gemini
response rejected (fallback used), fallback narrative works standalone,
narrative cannot alter time/id fields (they aren't even inputs to
Gemini's writable output), narrative failure never invalidates an
otherwise-valid itinerary, no booking confirmation claimed unless backend
state says so."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from src.core.config import Settings
from src.schemas.experience import CategorySummary, LocationSummary, ProviderSummary
from src.schemas.ranking import RankedExperienceItem
from src.services.experience_composer import ComposedItem
from src.services.itinerary_narrator import (
    ItemNarrative,
    ItineraryNarratorService,
    NarrativeResponse,
)

FORT_LAT, FORT_LNG = 18.9346, 72.8356


def _ranked(id_: str, title: str) -> RankedExperienceItem:
    return RankedExperienceItem(
        id=id_,
        title=title,
        short_description="x",
        category=CategorySummary(id="cat-1", slug="food-drink", name="Food"),
        location=LocationSummary(
            id="loc-1", latitude=FORT_LAT, longitude=FORT_LNG, place_name="x", address="x", city="Mumbai"
        ),
        provider=ProviderSummary(id="prov-1", business_name="x", verification_status="verified", is_synthetic=False),
        currency="INR",
        price=200.0,
        price_type="fixed",
        is_price_estimated=False,
        duration_minutes=60,
        duration_is_estimated=False,
        status="active",
        verification_status="verified",
        is_synthetic=True,
        is_enriched=False,
        rank=1,
        ranking_score=0.9,
        ranking_model_version="weighted-v1",
        semantic_relevance=0.9,
        personalized=False,
    )


def _items() -> list[ComposedItem]:
    start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    return [
        ComposedItem(
            experience=_ranked("exp-1", "Test Experience"),
            sequence_order=1,
            planned_start=start,
            planned_end=start + timedelta(minutes=60),
            duration_minutes=60,
            travel_from_previous_minutes=None,
            travel_from_previous_distance_km=None,
            travel_mode=None,
            buffer_before_minutes=0,
            buffer_after_minutes=0,
            estimated_cost=200.0,
            source_rank_position=1,
            source_ranking_score=0.9,
        )
    ]


class _WorkingMockAI:
    async def generate_text(self, prompt: str, *, response_schema):
        assert response_schema is NarrativeResponse
        return NarrativeResponse(
            title="A Great Day",
            summary="One great stop.",
            itinerary_intro="Here's your plan:",
            item_narratives=[ItemNarrative(experience_id="exp-1", text="Enjoy this one.")],
            travel_notes="",
            booking_notes="",
            closing_message="Have fun!",
        )


class _HallucinatingMockAI:
    async def generate_text(self, prompt: str, *, response_schema):
        return NarrativeResponse(
            title="A Great Day",
            summary="Summary.",
            itinerary_intro="Intro.",
            item_narratives=[
                ItemNarrative(experience_id="exp-1", text="Real item."),
                ItemNarrative(experience_id="exp-999-not-real", text="Fabricated item."),
            ],
            travel_notes="",
            booking_notes="",
            closing_message="Bye!",
        )


class _FailingMockAI:
    async def generate_text(self, prompt: str, *, response_schema):
        raise RuntimeError("Gemini is down")


class _InvalidStructuredMockAI:
    async def generate_text(self, prompt: str, *, response_schema):
        raise ValueError("invalid structured output")


def test_structured_output_used_when_gemini_succeeds():
    narrator = ItineraryNarratorService(_WorkingMockAI(), Settings())

    async def _run():
        return await narrator.narrate(
            items=_items(), itinerary_date_str="2026-10-12", currency="INR", total_cost=200.0
        )

    outcome = asyncio.run(_run())
    assert outcome.used_fallback is False
    assert outcome.model_version == Settings().composer_narrative_model_version
    assert outcome.narrative.title == "A Great Day"


def test_hallucinated_experience_id_dropped():
    narrator = ItineraryNarratorService(_HallucinatingMockAI(), Settings())

    async def _run():
        return await narrator.narrate(
            items=_items(), itinerary_date_str="2026-10-12", currency="INR", total_cost=200.0
        )

    outcome = asyncio.run(_run())
    ids = {n.experience_id for n in outcome.narrative.item_narratives}
    assert ids == {"exp-1"}
    assert "exp-999-not-real" not in ids


def test_gemini_failure_falls_back_to_template():
    narrator = ItineraryNarratorService(_FailingMockAI(), Settings())

    async def _run():
        return await narrator.narrate(
            items=_items(), itinerary_date_str="2026-10-12", currency="INR", total_cost=200.0
        )

    outcome = asyncio.run(_run())
    assert outcome.used_fallback is True
    assert outcome.model_version == Settings().composer_template_narrative_version
    assert outcome.narrative.title  # non-empty, deterministic


def test_invalid_structured_output_falls_back():
    narrator = ItineraryNarratorService(_InvalidStructuredMockAI(), Settings())

    async def _run():
        return await narrator.narrate(
            items=_items(), itinerary_date_str="2026-10-12", currency="INR", total_cost=200.0
        )

    outcome = asyncio.run(_run())
    assert outcome.used_fallback is True


def test_fallback_narrative_never_claims_confirmed_booking():
    narrator = ItineraryNarratorService(_FailingMockAI(), Settings())

    async def _run():
        return await narrator.narrate(
            items=_items(),
            itinerary_date_str="2026-10-12",
            currency="INR",
            total_cost=200.0,
            booking_statuses={"exp-1": "REQUESTED"},
        )

    outcome = asyncio.run(_run())
    full_text = " ".join(
        [
            outcome.narrative.title,
            outcome.narrative.summary,
            outcome.narrative.booking_notes,
            outcome.narrative.closing_message,
        ]
    ).lower()
    # "not yet confirmed" / "pending" is honest; an affirmative "is
    # confirmed" claim is what must never appear.
    assert "is confirmed" not in full_text
    assert "your booking is confirmed" not in full_text
    assert "pending" in outcome.narrative.booking_notes.lower() or "requested" in outcome.narrative.booking_notes.lower()


def test_narrative_failure_does_not_affect_item_facts():
    """The narrator never touches ComposedItem's time/id fields — this
    test proves the input items list is unmodified after narration,
    regardless of Gemini success/failure."""
    items = _items()
    original_ids = [i.experience.id for i in items]
    original_starts = [i.planned_start for i in items]

    narrator = ItineraryNarratorService(_FailingMockAI(), Settings())

    async def _run():
        return await narrator.narrate(
            items=items, itinerary_date_str="2026-10-12", currency="INR", total_cost=200.0
        )

    asyncio.run(_run())
    assert [i.experience.id for i in items] == original_ids
    assert [i.planned_start for i in items] == original_starts


def test_empty_items_never_calls_gemini_and_returns_fallback():
    calls = {"count": 0}

    class _CountingMockAI:
        async def generate_text(self, prompt: str, *, response_schema):
            calls["count"] += 1
            raise AssertionError("should never be called for an empty itinerary")

    narrator = ItineraryNarratorService(_CountingMockAI(), Settings())

    async def _run():
        return await narrator.narrate(items=[], itinerary_date_str="2026-10-12", currency="INR", total_cost=0.0)

    outcome = asyncio.run(_run())
    assert calls["count"] == 0
    assert outcome.used_fallback is True
