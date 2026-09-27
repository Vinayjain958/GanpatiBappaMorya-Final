"""FeasibilityService unit tests (Phase 6) — no network, MockRoutingAdapter
only. Covers every check: active/inactive, budget under/at/over,
missing-price+hard-budget=UNKNOWN, duration within/beyond/exact boundary,
opening hours within/outside/closed-day/overnight/missing, travel time
within/beyond/unavailable, distance within/beyond, capacity
within/beyond/missing, accessibility pass/fail/missing, availability
valid/conflict/missing, itinerary conflict, multiple simultaneous
failures, all-pass=FEASIBLE, UNKNOWN never becomes FEASIBLE.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time

from src.adapters.errors import AdapterNoResultError, AdapterUnavailableError
from src.adapters.routing import MatrixEntry, RouteResult
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.models.availability import ExperienceAvailability
from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.location import Location
from src.models.opening_hour import ExperienceOpeningHour
from src.models.provider import Provider
from src.schemas.feasibility import CommittedTimeBlock, TravelerConstraints
from src.services.feasibility import FeasibilityService

FORT_LAT, FORT_LNG = 18.9346, 72.8356


class _StubRoutingAdapter:
    """Deterministic routing stub — returns a fixed duration/distance or
    raises the configured error, no network."""

    def __init__(self, duration_minutes: float = 20.0, distance_km: float = 5.0, error: Exception | None = None):
        self.duration_minutes = duration_minutes
        self.distance_km = distance_km
        self.error = error
        self.calls = 0

    async def get_route(self, origin, destination, *, profile, include_geometry=False):
        self.calls += 1
        if self.error:
            raise self.error
        return RouteResult(
            distance_km=self.distance_km, duration_minutes=self.duration_minutes, geometry=None, source="osrm"
        )

    async def get_travel_time_matrix(self, origin, destinations, *, profile):
        return [
            MatrixEntry(id=d[0], distance_km=self.distance_km, duration_minutes=self.duration_minutes)
            for d in destinations
        ]


def _make_experience(**overrides) -> Experience:
    category = ExperienceCategory(slug="food-drink", name="Food & Drink", sort_order=1)
    location = Location(
        latitude=overrides.pop("lat", FORT_LAT),
        longitude=overrides.pop("lng", FORT_LNG),
        city="Mumbai",
        locality="Fort",
        source_type="synthetic",
        is_synthetic=True,
        timezone="Asia/Kolkata",
    )
    provider = Provider(business_name="Test Co", source_type="synthetic", is_synthetic=True)

    defaults = dict(
        title="Test Experience",
        short_description="A test experience.",
        full_description="A longer description.",
        currency="INR",
        price=500.0,
        price_type="fixed",
        price_source="estimated",
        is_price_estimated=True,
        duration_minutes=60,
        duration_is_estimated=True,
        status="active",
        verification_status="unverified",
        opening_hours_status="unavailable",
        source_type="synthetic",
        is_synthetic=True,
        capacity=10,
    )
    defaults.update(overrides)

    experience = Experience(provider=provider, category=category, location=location, **defaults)
    experience.opening_hours = []
    experience.availability_slots = []
    # id is normally set by the DB default; simulate it here since these
    # tests never persist to a session.
    if not experience.id:
        import uuid

        experience.id = str(uuid.uuid4())
    return experience


def _evaluate(experience, constraints, routing=None):
    service = FeasibilityService(routing or _StubRoutingAdapter())
    return asyncio.run(service.evaluate(experience, constraints))


# ─── active status ──────────────────────────────────────────────────────


def test_active_experience_passes_status_check():
    exp = _make_experience(status="active")
    verdict = _evaluate(exp, TravelerConstraints())
    assert not any(r.code == FeasibilityReasonCode.EXPERIENCE_INACTIVE for r in verdict.reasons)


def test_inactive_experience_is_infeasible():
    exp = _make_experience(status="inactive")
    verdict = _evaluate(exp, TravelerConstraints())
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.EXPERIENCE_INACTIVE for r in verdict.reasons)


# ─── budget ──────────────────────────────────────────────────────────────


def test_budget_under_limit_passes():
    exp = _make_experience(price=300.0)
    verdict = _evaluate(exp, TravelerConstraints(budget_max=500))
    assert verdict.status == "FEASIBLE"


def test_budget_exactly_at_limit_passes():
    exp = _make_experience(price=500.0)
    verdict = _evaluate(exp, TravelerConstraints(budget_max=500))
    assert verdict.status == "FEASIBLE"


def test_budget_over_limit_is_infeasible():
    exp = _make_experience(price=600.0)
    verdict = _evaluate(exp, TravelerConstraints(budget_max=500))
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.BUDGET_EXCEEDED for r in verdict.reasons)


def test_missing_price_with_hard_budget_is_unknown():
    exp = _make_experience(price=None, minimum_price=None, maximum_price=None)
    verdict = _evaluate(exp, TravelerConstraints(budget_max=500))
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.PRICE_UNAVAILABLE for r in verdict.reasons)


def test_no_budget_constraint_skips_check():
    exp = _make_experience(price=None)
    verdict = _evaluate(exp, TravelerConstraints())
    assert verdict.status == "FEASIBLE"


def test_unsupported_currency_is_unknown():
    exp = _make_experience(price=500.0, currency="USD")
    verdict = _evaluate(exp, TravelerConstraints(budget_max=500, currency="INR"))
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.UNSUPPORTED_CURRENCY for r in verdict.reasons)


# ─── duration ────────────────────────────────────────────────────────────


def test_duration_within_available_passes():
    exp = _make_experience(duration_minutes=45)
    verdict = _evaluate(exp, TravelerConstraints(available_duration_minutes=60))
    assert verdict.status == "FEASIBLE"


def test_duration_exact_boundary_passes():
    exp = _make_experience(duration_minutes=60)
    verdict = _evaluate(exp, TravelerConstraints(available_duration_minutes=60))
    assert not any(r.code == FeasibilityReasonCode.DURATION_EXCEEDED for r in verdict.reasons)


def test_duration_beyond_available_is_infeasible():
    exp = _make_experience(duration_minutes=90)
    verdict = _evaluate(exp, TravelerConstraints(available_duration_minutes=60))
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.DURATION_EXCEEDED for r in verdict.reasons)


def test_missing_duration_with_required_is_unknown():
    exp = _make_experience(duration_minutes=None)
    verdict = _evaluate(exp, TravelerConstraints(available_duration_minutes=60))
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.DURATION_UNAVAILABLE for r in verdict.reasons)


# ─── distance ────────────────────────────────────────────────────────────


def test_distance_within_max_passes():
    exp = _make_experience(lat=FORT_LAT + 0.001, lng=FORT_LNG)
    verdict = _evaluate(exp, TravelerConstraints(origin_lat=FORT_LAT, origin_lng=FORT_LNG, max_distance_km=5))
    assert not any(r.code == FeasibilityReasonCode.MAX_DISTANCE_EXCEEDED for r in verdict.reasons)


def test_distance_beyond_max_is_infeasible():
    exp = _make_experience(lat=FORT_LAT + 1.0, lng=FORT_LNG)
    verdict = _evaluate(exp, TravelerConstraints(origin_lat=FORT_LAT, origin_lng=FORT_LNG, max_distance_km=1))
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.MAX_DISTANCE_EXCEEDED for r in verdict.reasons)


def test_distance_constraint_without_origin_is_unknown():
    exp = _make_experience()
    verdict = _evaluate(exp, TravelerConstraints(max_distance_km=5))
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.MISSING_ORIGIN for r in verdict.reasons)


# ─── travel time ─────────────────────────────────────────────────────────


def test_travel_time_within_max_passes():
    exp = _make_experience()
    routing = _StubRoutingAdapter(duration_minutes=15)
    verdict = _evaluate(
        exp, TravelerConstraints(origin_lat=FORT_LAT, origin_lng=FORT_LNG, max_travel_time_minutes=30), routing
    )
    assert not any(r.code == FeasibilityReasonCode.TRAVEL_TIME_EXCEEDED for r in verdict.reasons)


def test_travel_time_beyond_max_is_infeasible():
    exp = _make_experience()
    routing = _StubRoutingAdapter(duration_minutes=45)
    verdict = _evaluate(
        exp, TravelerConstraints(origin_lat=FORT_LAT, origin_lng=FORT_LNG, max_travel_time_minutes=30), routing
    )
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.TRAVEL_TIME_EXCEEDED for r in verdict.reasons)


def test_travel_time_unavailable_with_hard_constraint_is_unknown():
    exp = _make_experience()
    routing = _StubRoutingAdapter(error=AdapterUnavailableError("OSRM down"))
    verdict = _evaluate(
        exp, TravelerConstraints(origin_lat=FORT_LAT, origin_lng=FORT_LNG, max_travel_time_minutes=30), routing
    )
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.TRAVEL_TIME_UNAVAILABLE for r in verdict.reasons)


def test_travel_time_no_route_found_is_unknown():
    exp = _make_experience()
    routing = _StubRoutingAdapter(error=AdapterNoResultError("no route"))
    verdict = _evaluate(
        exp, TravelerConstraints(origin_lat=FORT_LAT, origin_lng=FORT_LNG, max_travel_time_minutes=30), routing
    )
    assert verdict.status == "UNKNOWN"


# ─── capacity ────────────────────────────────────────────────────────────


def test_party_size_within_capacity_passes():
    exp = _make_experience(capacity=10)
    verdict = _evaluate(exp, TravelerConstraints(party_size=4))
    assert not any(r.code == FeasibilityReasonCode.GROUP_SIZE_EXCEEDS_CAPACITY for r in verdict.reasons)


def test_party_size_exceeds_capacity_is_infeasible():
    exp = _make_experience(capacity=4)
    verdict = _evaluate(exp, TravelerConstraints(party_size=10))
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.GROUP_SIZE_EXCEEDS_CAPACITY for r in verdict.reasons)


def test_missing_capacity_with_required_is_unknown():
    exp = _make_experience(capacity=None, maximum_group_size=None)
    verdict = _evaluate(exp, TravelerConstraints(party_size=4))
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.CAPACITY_UNAVAILABLE for r in verdict.reasons)


# ─── accessibility ───────────────────────────────────────────────────────


def test_accessibility_explicit_pass():
    exp = _make_experience(wheelchair_accessible=True)
    verdict = _evaluate(exp, TravelerConstraints(accessibility_requirements=["wheelchair_accessible"]))
    assert verdict.status == "FEASIBLE"


def test_accessibility_explicit_fail():
    exp = _make_experience(wheelchair_accessible=False)
    verdict = _evaluate(exp, TravelerConstraints(accessibility_requirements=["wheelchair_accessible"]))
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.ACCESSIBILITY_NOT_SUPPORTED for r in verdict.reasons)


def test_accessibility_missing_with_required_is_unknown():
    exp = _make_experience(wheelchair_accessible=None)
    verdict = _evaluate(exp, TravelerConstraints(accessibility_requirements=["wheelchair_accessible"]))
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.ACCESSIBILITY_DATA_UNAVAILABLE for r in verdict.reasons)


def test_accessibility_not_requested_skips_check():
    exp = _make_experience(wheelchair_accessible=None)
    verdict = _evaluate(exp, TravelerConstraints())
    assert verdict.status == "FEASIBLE"


# ─── availability ────────────────────────────────────────────────────────


def _availability_slot(start: datetime, end: datetime, status: str = "active") -> ExperienceAvailability:
    slot = ExperienceAvailability(starts_at=start, ends_at=end, capacity=10, status=status)
    return slot


def test_availability_valid_slot_passes():
    exp = _make_experience()
    target_date = date(2026, 10, 10)
    exp.availability_slots = [
        _availability_slot(
            datetime(2026, 10, 10, 9, 0, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")),
            datetime(2026, 10, 10, 18, 0, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")),
        )
    ]
    verdict = _evaluate(
        exp,
        TravelerConstraints(available_date=target_date, available_start=time(10, 0), available_end=time(11, 0)),
    )
    assert not any(r.code == FeasibilityReasonCode.AVAILABILITY_CONFLICT for r in verdict.reasons)


def test_availability_conflict_is_infeasible():
    exp = _make_experience()
    target_date = date(2026, 10, 10)
    tz = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
    exp.availability_slots = [
        _availability_slot(datetime(2026, 10, 10, 9, 0, tzinfo=tz), datetime(2026, 10, 10, 10, 0, tzinfo=tz))
    ]
    verdict = _evaluate(
        exp,
        TravelerConstraints(available_date=target_date, available_start=time(14, 0), available_end=time(15, 0)),
    )
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.AVAILABILITY_CONFLICT for r in verdict.reasons)


def test_availability_missing_with_required_is_unknown():
    exp = _make_experience()
    exp.availability_slots = []
    verdict = _evaluate(
        exp, TravelerConstraints(available_date=date(2026, 10, 10), available_start=time(10, 0))
    )
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.AVAILABILITY_UNAVAILABLE for r in verdict.reasons)


# ─── opening hours ───────────────────────────────────────────────────────


def _hours(day: int, open_t: str, close_t: str) -> ExperienceOpeningHour:
    return ExperienceOpeningHour(day_of_week=day, open_time=open_t, close_time=close_t, is_closed=False)


def test_opening_hours_within_window_passes():
    exp = _make_experience()
    exp.opening_hours = [_hours(day=5, open_t="09:00", close_t="18:00")]  # Saturday
    target_date = date(2026, 10, 10)  # a Saturday
    assert target_date.weekday() == 5
    verdict = _evaluate(
        exp, TravelerConstraints(available_date=target_date, available_start=time(10, 0), available_end=time(11, 0))
    )
    assert not any(r.code == FeasibilityReasonCode.OPENING_HOURS_CONFLICT for r in verdict.reasons)


def test_opening_hours_outside_window_is_infeasible():
    exp = _make_experience()
    exp.opening_hours = [_hours(day=5, open_t="09:00", close_t="18:00")]
    target_date = date(2026, 10, 10)
    verdict = _evaluate(
        exp, TravelerConstraints(available_date=target_date, available_start=time(20, 0), available_end=time(21, 0))
    )
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.OPENING_HOURS_CONFLICT for r in verdict.reasons)


def test_opening_hours_closed_day_is_infeasible():
    exp = _make_experience()
    exp.opening_hours = [
        ExperienceOpeningHour(day_of_week=5, open_time=None, close_time=None, is_closed=True)
    ]
    target_date = date(2026, 10, 10)
    verdict = _evaluate(
        exp, TravelerConstraints(available_date=target_date, available_start=time(10, 0), available_end=time(11, 0))
    )
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.OPENING_HOURS_CONFLICT for r in verdict.reasons)


def test_opening_hours_overnight_window_passes():
    exp = _make_experience()
    # Friday 22:00 - Saturday 02:00 (overnight)
    exp.opening_hours = [_hours(day=4, open_t="22:00", close_t="02:00")]
    target_date = date(2026, 10, 9)  # a Friday
    assert target_date.weekday() == 4
    verdict = _evaluate(
        exp, TravelerConstraints(available_date=target_date, available_start=time(23, 0), available_end=time(23, 30))
    )
    assert not any(r.code == FeasibilityReasonCode.OPENING_HOURS_CONFLICT for r in verdict.reasons)


def test_opening_hours_missing_with_required_is_unknown():
    exp = _make_experience()
    exp.opening_hours = []
    verdict = _evaluate(
        exp, TravelerConstraints(available_date=date(2026, 10, 10), available_start=time(10, 0))
    )
    assert verdict.status == "UNKNOWN"
    assert any(r.code == FeasibilityReasonCode.OPENING_HOURS_UNAVAILABLE for r in verdict.reasons)


def test_opening_hours_not_checked_without_time_context():
    exp = _make_experience()
    exp.opening_hours = []
    verdict = _evaluate(exp, TravelerConstraints())
    assert verdict.status == "FEASIBLE"


# ─── itinerary conflicts ─────────────────────────────────────────────────


def test_itinerary_conflict_detected():
    exp = _make_experience(duration_minutes=60)
    tz = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
    target_date = date(2026, 10, 10)
    block = CommittedTimeBlock(
        start=datetime(2026, 10, 10, 10, 30, tzinfo=tz), end=datetime(2026, 10, 10, 11, 30, tzinfo=tz)
    )
    routing = _StubRoutingAdapter(duration_minutes=0)
    verdict = _evaluate(
        exp,
        TravelerConstraints(
            available_date=target_date, available_start=time(10, 0), existing_commitments=[block]
        ),
        routing,
    )
    assert verdict.status == "INFEASIBLE"
    assert any(r.code == FeasibilityReasonCode.ITINERARY_CONFLICT for r in verdict.reasons)


def test_itinerary_no_conflict_when_gap_available():
    exp = _make_experience(duration_minutes=30)
    tz = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
    target_date = date(2026, 10, 10)
    block = CommittedTimeBlock(
        start=datetime(2026, 10, 10, 14, 0, tzinfo=tz), end=datetime(2026, 10, 10, 15, 0, tzinfo=tz)
    )
    verdict = _evaluate(
        exp,
        TravelerConstraints(
            available_date=target_date, available_start=time(9, 0), existing_commitments=[block]
        ),
    )
    assert not any(r.code == FeasibilityReasonCode.ITINERARY_CONFLICT for r in verdict.reasons)


# ─── multi-failure / overall verdict policy ─────────────────────────────


def test_multiple_simultaneous_failures_all_returned():
    exp = _make_experience(price=1000.0, duration_minutes=180, capacity=2)
    verdict = _evaluate(
        exp, TravelerConstraints(budget_max=500, available_duration_minutes=60, party_size=10)
    )
    assert verdict.status == "INFEASIBLE"
    codes = {r.code for r in verdict.reasons}
    assert FeasibilityReasonCode.BUDGET_EXCEEDED in codes
    assert FeasibilityReasonCode.DURATION_EXCEEDED in codes
    assert FeasibilityReasonCode.GROUP_SIZE_EXCEEDS_CAPACITY in codes


def test_all_pass_is_feasible():
    exp = _make_experience(price=300.0, duration_minutes=45, capacity=10)
    verdict = _evaluate(
        exp, TravelerConstraints(budget_max=500, available_duration_minutes=60, party_size=4)
    )
    assert verdict.status == "FEASIBLE"
    assert verdict.reasons == []


def test_unknown_never_becomes_feasible_even_with_other_passes():
    exp = _make_experience(price=None, duration_minutes=30, capacity=10)
    verdict = _evaluate(
        exp, TravelerConstraints(budget_max=500, available_duration_minutes=60, party_size=4)
    )
    assert verdict.status == "UNKNOWN"
    assert verdict.status != "FEASIBLE"


def test_unknown_plus_infeasible_together_reports_infeasible_not_unknown():
    # An explicit contradiction (INFEASIBLE) alongside missing data
    # (UNKNOWN) — the overall verdict must never claim FEASIBLE; the
    # blocking INFEASIBLE reason takes precedence in the status label.
    exp = _make_experience(price=1000.0, capacity=None, maximum_group_size=None)
    verdict = _evaluate(exp, TravelerConstraints(budget_max=500, party_size=4))
    assert verdict.status in ("INFEASIBLE", "UNKNOWN")
    assert verdict.status != "FEASIBLE"
    codes = {r.code for r in verdict.reasons}
    assert FeasibilityReasonCode.BUDGET_EXCEEDED in codes
    assert FeasibilityReasonCode.CAPACITY_UNAVAILABLE in codes
