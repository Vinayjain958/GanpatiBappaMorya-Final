"""DiscoveryPipelineService integration test (Phase 6).

Three candidates seeded with real ExperienceEmbedding rows (via
MockEmbeddingAdapter, deterministic — no network):
  A: high textual similarity to the query but over budget -> excluded
  B: lower similarity but all constraints pass -> survives
  C: high similarity but outside the requested time window -> excluded

Only B should end up in `items`.
"""

from __future__ import annotations

import asyncio

import pytest

from src.adapters.embedding import MockEmbeddingAdapter
from src.adapters.routing import MockRoutingAdapter
from src.core.config import Settings
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.models.availability import ExperienceAvailability
from src.models.category import ExperienceCategory
from src.models.embedding import ExperienceEmbedding
from src.models.experience import Experience
from src.models.location import Location
from src.models.opening_hour import ExperienceOpeningHour
from src.models.provider import Provider
from src.schemas.feasibility import TravelerConstraints
from src.services.discovery_pipeline import DiscoveryPipelineService
from src.services.embedding_text import build_experience_document_text

FORT_LAT, FORT_LNG = 18.9346, 72.8356


@pytest.fixture()
def pipeline_dataset(session_factory):
    async def _seed():
        async with session_factory() as session:
            category = ExperienceCategory(slug="food-drink", name="Food & Drink", sort_order=1)
            session.add(category)
            await session.flush()

            provider = Provider(business_name="Pipeline Test Co", source_type="synthetic", is_synthetic=True)
            session.add(provider)
            await session.flush()

            location = Location(
                latitude=FORT_LAT, longitude=FORT_LNG, city="Mumbai", locality="Fort",
                source_type="synthetic", is_synthetic=True, timezone="Asia/Kolkata",
            )
            session.add(location)
            await session.flush()

            # A: over budget
            exp_a = Experience(
                provider=provider, category=category, location=location,
                title="Street Food Walking Tour", short_description="A tasty street food walk.",
                full_description="Explore the best street food stalls near Fort.",
                currency="INR", price=2000.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=90, duration_is_estimated=True,
                status="active", verification_status="unverified", opening_hours_status="unavailable",
                source_type="synthetic", is_synthetic=True, capacity=10,
            )
            # B: all constraints pass
            exp_b = Experience(
                provider=provider, category=category, location=location,
                title="Local Food Tasting Session", short_description="A budget-friendly food tasting.",
                full_description="Sample local dishes on a budget-friendly tasting session.",
                currency="INR", price=400.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=60, duration_is_estimated=True,
                status="active", verification_status="unverified", opening_hours_status="unavailable",
                source_type="synthetic", is_synthetic=True, capacity=10,
            )
            # C: outside opening hours
            exp_c = Experience(
                provider=provider, category=category, location=location,
                title="Street Food Night Market", short_description="A night-only street food market.",
                full_description="A street food market open only late at night near Fort.",
                currency="INR", price=300.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=60, duration_is_estimated=True,
                status="active", verification_status="unverified", opening_hours_status="hours_known",
                source_type="synthetic", is_synthetic=True, capacity=10,
            )
            session.add_all([exp_a, exp_b, exp_c])
            await session.flush()

            # B is open all day every day; C is only open 22:00-23:59.
            for day in range(7):
                session.add(
                    ExperienceOpeningHour(
                        experience_id=exp_b.id, day_of_week=day, open_time="00:00", close_time="23:59",
                        is_closed=False,
                    )
                )
                session.add(
                    ExperienceOpeningHour(
                        experience_id=exp_c.id, day_of_week=day, open_time="22:00", close_time="23:59",
                        is_closed=False,
                    )
                )

            # B has an open-ended active availability slot covering the
            # test's requested window; A and C intentionally have none
            # (their exclusion is driven by budget/opening-hours instead).
            import datetime as _dt

            session.add(
                ExperienceAvailability(
                    experience_id=exp_b.id,
                    starts_at=_dt.datetime(2026, 10, 1, tzinfo=_dt.UTC),
                    ends_at=_dt.datetime(2026, 12, 31, tzinfo=_dt.UTC),
                    capacity=10,
                    status="active",
                )
            )

            adapter = MockEmbeddingAdapter()
            query_text = "street food walking tour near Fort"
            for exp in (exp_a, exp_b, exp_c):
                doc = build_experience_document_text(exp)
                vector = await adapter.embed_document(doc.title, doc.text)
                session.add(
                    ExperienceEmbedding(
                        experience_id=exp.id, embedding=vector, embedding_model="mock",
                        embedding_dimensions=len(vector), source_content_hash=doc.content_hash,
                    )
                )
            await session.commit()

            return {"a": exp_a.id, "b": exp_b.id, "c": exp_c.id, "query": query_text}

    return asyncio.run(_seed())


def test_only_feasible_candidate_survives(session_factory, pipeline_dataset):
    async def _run():
        async with session_factory() as session:
            settings = Settings(semantic_candidate_pool_size=10, semantic_max_candidate_pool_size=50)
            pipeline = DiscoveryPipelineService(
                session, settings, MockEmbeddingAdapter(), MockRoutingAdapter()
            )
            result = await pipeline.run(
                raw_query=pipeline_dataset["query"],
                constraints=TravelerConstraints(
                    budget_max=500,
                    available_date=__import__("datetime").date(2026, 10, 12),  # a Monday
                    available_start=__import__("datetime").time(10, 0),
                    available_end=__import__("datetime").time(11, 0),
                ),
                limit=10,
            )
            return result

    result = asyncio.run(_run())

    surviving_ids = {item.experience_id for item in result.items}
    assert surviving_ids == {pipeline_dataset["b"]}
    assert result.feasible_count == 1
    assert result.excluded_count == 2
    assert result.retrieval_mode == "sqlite_python_semantic"

    # Verify the excluded ones for the right reasons.
    excluded_ids_to_reasons = {
        entry["experience_id"]: entry["reasons"] for entry in result.excluded_summary.sample
    }
    assert FeasibilityReasonCode.BUDGET_EXCEEDED.value in excluded_ids_to_reasons[pipeline_dataset["a"]]
    assert FeasibilityReasonCode.OPENING_HOURS_CONFLICT.value in excluded_ids_to_reasons[pipeline_dataset["c"]]


def test_all_infeasible_returns_empty_items_not_forced_result(session_factory, pipeline_dataset):
    async def _run():
        async with session_factory() as session:
            settings = Settings(semantic_candidate_pool_size=10, semantic_max_candidate_pool_size=50)
            pipeline = DiscoveryPipelineService(
                session, settings, MockEmbeddingAdapter(), MockRoutingAdapter()
            )
            return await pipeline.run(
                raw_query=pipeline_dataset["query"],
                constraints=TravelerConstraints(budget_max=1),  # nothing can be this cheap
                limit=10,
            )

    result = asyncio.run(_run())
    assert result.items == []
    assert result.feasible_count == 0
    assert result.excluded_count == 3
