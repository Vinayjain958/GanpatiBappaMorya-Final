"""ItineraryValidatorService tests (Phase 8) — DB-backed since it re-runs
FeasibilityService against real Experience rows."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from src.adapters.routing import MockRoutingAdapter
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.models.availability import ExperienceAvailability
from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.location import Location
from src.models.opening_hour import ExperienceOpeningHour
from src.models.provider import Provider
from src.schemas.experience import CategorySummary, LocationSummary, ProviderSummary
from src.schemas.ranking import RankedExperienceItem
from src.services.experience_composer import ComposedItem
from src.services.itinerary_validator import ItineraryValidatorService

FORT_LAT, FORT_LNG = 18.9346, 72.8356


@pytest.fixture()
def validator_dataset(session_factory):
    async def _seed():
        async with session_factory() as session:
            category = ExperienceCategory(slug="food-drink", name="Food & Drink", sort_order=1)
            session.add(category)
            await session.flush()

            provider = Provider(business_name="Validator Test Co", source_type="synthetic", is_synthetic=True)
            session.add(provider)
            await session.flush()

            location = Location(
                latitude=FORT_LAT, longitude=FORT_LNG, city="Mumbai", locality="Fort",
                source_type="synthetic", is_synthetic=True, timezone="Asia/Kolkata",
            )
            session.add(location)
            await session.flush()

            # Always-open, always-feasible experience.
            exp_open = Experience(
                provider=provider, category=category, location=location,
                title="Always Open Experience", short_description="Open all day.",
                full_description="Open all day every day.",
                currency="INR", price=200.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=60, duration_is_estimated=True,
                status="active", verification_status="unverified", opening_hours_status="hours_known",
                source_type="synthetic", is_synthetic=True, capacity=10,
            )
            # Only open late at night — will conflict with a daytime slot.
            exp_night_only = Experience(
                provider=provider, category=category, location=location,
                title="Night Only Experience", short_description="Open only at night.",
                full_description="Open only at night.",
                currency="INR", price=200.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=60, duration_is_estimated=True,
                status="active", verification_status="unverified", opening_hours_status="hours_known",
                source_type="synthetic", is_synthetic=True, capacity=10,
            )
            # Inactive experience — never feasible.
            exp_inactive = Experience(
                provider=provider, category=category, location=location,
                title="Inactive Experience", short_description="Not active.",
                full_description="Not active.",
                currency="INR", price=200.0, price_type="fixed", price_source="estimated",
                is_price_estimated=True, duration_minutes=60, duration_is_estimated=True,
                status="inactive", verification_status="unverified", opening_hours_status="hours_known",
                source_type="synthetic", is_synthetic=True, capacity=10,
            )
            session.add_all([exp_open, exp_night_only, exp_inactive])
            await session.flush()

            for day in range(7):
                session.add(
                    ExperienceOpeningHour(
                        experience_id=exp_open.id, day_of_week=day, open_time="00:00", close_time="23:59",
                        is_closed=False,
                    )
                )
                session.add(
                    ExperienceOpeningHour(
                        experience_id=exp_night_only.id, day_of_week=day, open_time="22:00", close_time="23:59",
                        is_closed=False,
                    )
                )
            # exp_open also has an open-ended active availability slot
            # covering the whole test window, so it is unambiguously
            # FEASIBLE (not UNKNOWN) for the "valid itinerary" test case.
            session.add(
                ExperienceAvailability(
                    experience_id=exp_open.id,
                    starts_at=datetime(2026, 10, 1, tzinfo=UTC),
                    ends_at=datetime(2026, 12, 31, tzinfo=UTC),
                    capacity=10,
                    status="active",
                )
            )
            await session.commit()

            return {
                "open_id": exp_open.id,
                "night_only_id": exp_night_only.id,
                "inactive_id": exp_inactive.id,
            }

    return asyncio.run(_seed())


def _stub_ranked(*, exp_id: str, title: str, rank: int, price: float = 200.0) -> RankedExperienceItem:
    return RankedExperienceItem(
        id=exp_id,
        title=title,
        short_description="x",
        category=CategorySummary(id="cat-1", slug="food-drink", name="Food"),
        location=LocationSummary(
            id="loc-1", latitude=FORT_LAT, longitude=FORT_LNG, place_name="x", address="x", city="Mumbai"
        ),
        provider=ProviderSummary(id="prov-1", business_name="x", verification_status="verified", is_synthetic=False),
        currency="INR",
        price=price,
        price_type="fixed",
        is_price_estimated=False,
        duration_minutes=60,
        duration_is_estimated=False,
        status="active",
        verification_status="verified",
        is_synthetic=True,
        is_enriched=False,
        rank=rank,
        ranking_score=0.9,
        ranking_model_version="weighted-v1",
        semantic_relevance=0.9,
        personalized=False,
    )


def _composed(*, exp_id: str, title: str, start: datetime, duration_minutes: int = 60, travel_minutes=0.0, seq=1):
    return ComposedItem(
        experience=_stub_ranked(exp_id=exp_id, title=title, rank=seq),
        sequence_order=seq,
        planned_start=start,
        planned_end=start + timedelta(minutes=duration_minutes),
        duration_minutes=duration_minutes,
        travel_from_previous_minutes=travel_minutes,
        travel_from_previous_distance_km=0.0,
        travel_mode="driving",
        buffer_before_minutes=10,
        buffer_after_minutes=0,
        estimated_cost=200.0,
        source_rank_position=seq,
        source_ranking_score=0.9,
    )


def test_valid_itinerary_passes(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)  # Monday
            items = [_composed(exp_id=exp.id, title=exp.title, start=start)]
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=items,
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=3),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is True
    assert result.issues == []


def test_opening_hours_violation_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["night_only_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)  # daytime — experience only open at night
            items = [_composed(exp_id=exp.id, title=exp.title, start=start)]
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=items,
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=3),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE for i in result.issues)


def test_inactive_experience_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["inactive_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            items = [_composed(exp_id=exp.id, title=exp.title, start=start)]
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=items,
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=3),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE for i in result.issues)


def test_overlap_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            item1 = _composed(exp_id=exp.id, title=exp.title, start=start, duration_minutes=60, seq=1)
            # Second item starts before the first ends -> overlap.
            item2 = _composed(
                exp_id=exp.id, title=exp.title, start=start + timedelta(minutes=30), duration_minutes=60, seq=2
            )
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=[item1, item2],
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=5),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.SCHEDULE_OVERLAP for i in result.issues)
    assert any(i.code == FeasibilityReasonCode.DUPLICATE_EXPERIENCE for i in result.issues)


def test_budget_exceeded_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            items = [_composed(exp_id=exp.id, title=exp.title, start=start)]
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=items,
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=3),
                max_budget=50,  # experience costs 200
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    codes = {i.code for i in result.issues}
    assert FeasibilityReasonCode.ITINERARY_BUDGET_EXCEEDED in codes or FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE in codes


def test_invalid_duration_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            item = _composed(exp_id=exp.id, title=exp.title, start=start)
            item.planned_end = item.planned_start  # zero duration -> invalid
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=[item],
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=3),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.SCHEDULE_NOT_CHRONOLOGICAL for i in result.issues)


def test_unknown_travel_time_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            item1 = _composed(exp_id=exp.id, title=exp.title, start=start, seq=1)
            item2 = _composed(
                exp_id=exp.id, title=exp.title, start=start + timedelta(minutes=90), seq=2
            )
            item2.experience = _stub_ranked(exp_id=exp.id + "-dup", title="Second", rank=2)
            item2.travel_from_previous_minutes = None  # UNKNOWN transition
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=[item1, item2],
                experiences_by_id={exp.id: exp, exp.id + "-dup": exp},
                requested_start=start,
                requested_end=start + timedelta(hours=5),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.TRAVEL_TRANSITION_IMPOSSIBLE for i in result.issues)


def test_empty_itinerary_rejected():
    async def _run():
        validator = ItineraryValidatorService(MockRoutingAdapter())
        return await validator.validate(
            items=[],
            experiences_by_id={},
            requested_start=datetime(2026, 10, 12, 9, 0, tzinfo=UTC),
            requested_end=datetime(2026, 10, 12, 18, 0, tzinfo=UTC),
            max_budget=None,
            max_experiences=None,
            party_size=None,
            travel_mode="driving",
        )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.ITINERARY_EMPTY for i in result.issues)


def test_outside_requested_window_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            item = _composed(exp_id=exp.id, title=exp.title, start=start)
            validator = ItineraryValidatorService(MockRoutingAdapter())
            # requested window ends before the item does.
            return await validator.validate(
                items=[item],
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(minutes=10),
                max_budget=None,
                max_experiences=None,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.OUTSIDE_REQUESTED_WINDOW for i in result.issues)


def test_count_limit_exceeded_rejected(session_factory, validator_dataset):
    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository

            exp = await ExperienceRepository(session).get_by_id(validator_dataset["open_id"])
            start = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
            item = _composed(exp_id=exp.id, title=exp.title, start=start)
            validator = ItineraryValidatorService(MockRoutingAdapter())
            return await validator.validate(
                items=[item],
                experiences_by_id={exp.id: exp},
                requested_start=start,
                requested_end=start + timedelta(hours=3),
                max_budget=None,
                max_experiences=0,
                party_size=None,
                travel_mode="driving",
            )

    result = asyncio.run(_run())
    assert result.valid is False
    assert any(i.code == FeasibilityReasonCode.ITINERARY_COUNT_LIMIT_EXCEEDED for i in result.issues)
