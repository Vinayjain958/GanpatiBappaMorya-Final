"""FeasibilityService — 100% deterministic feasibility verification (Phase 6).

NO LLM calls anywhere in this module. Every check either:
  - is not applicable (traveler did not request that constraint) -> skipped,
  - passes,
  - fails with an explicit contradiction -> INFEASIBLE reason, or
  - cannot be evaluated because required data is missing -> UNKNOWN reason.

UNKNOWN can never become FEASIBLE: `evaluate()` only returns status
FEASIBLE when zero blocking reasons of any kind (INFEASIBLE or UNKNOWN)
were produced. All applicable checks run — the engine never short-
circuits on the first failure — so callers see every blocking reason at
once (docs/DECISIONS.md ADR-041).

Check order is fixed and documented (not semantically load-bearing, just
reproducible): active status -> budget -> duration -> distance -> travel
time -> total time -> opening hours -> availability -> capacity ->
accessibility -> itinerary conflicts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from src.adapters.errors import AdapterError
from src.adapters.routing import RoutingAdapter
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.core.geo import haversine_km
from src.models.experience import Experience
from src.schemas.feasibility import (
    FeasibilityReason,
    FeasibilityVerdict,
    TravelerConstraints,
)

_DEFAULT_TZ = "Asia/Kolkata"


def _reason(
    code: FeasibilityReasonCode, constraint: str, message: str, *, evidence: dict[str, object] | None = None
) -> FeasibilityReason:
    return FeasibilityReason(
        code=code, constraint=constraint, message=message, blocking=True, evidence=evidence or {}
    )


def _effective_price(experience: Experience) -> float | None:
    if experience.price is not None:
        return experience.price
    if experience.minimum_price is not None and experience.maximum_price is not None:
        return experience.maximum_price  # conservative: worst case for a budget cap
    return experience.minimum_price if experience.minimum_price is not None else experience.maximum_price


class FeasibilityService:
    """Stateless — takes a RoutingAdapter for the travel-time check only;
    every other check is pure computation over stored data."""

    def __init__(self, routing_adapter: RoutingAdapter) -> None:
        self._routing = routing_adapter

    @classmethod
    def opening_hours_status(
        cls,
        experience: Experience,
        constraints: TravelerConstraints,
    ) -> tuple[Literal["open", "closed", "unknown"], list[FeasibilityReason]]:
        """Check only recorded operating hours for one planned visit window.

        Nearby alternatives need an opening-hours verdict without requiring
        separate price, capacity, or bookable-slot data. The full
        ``evaluate`` method remains the authoritative composition check.
        """
        reasons: list[FeasibilityReason] = []
        cls._check_opening_hours(experience, constraints, reasons)
        if any(reason.code == FeasibilityReasonCode.OPENING_HOURS_UNAVAILABLE for reason in reasons):
            return "unknown", reasons
        if reasons:
            return "closed", reasons
        return "open", reasons

    async def evaluate(
        self,
        experience: Experience,
        constraints: TravelerConstraints,
        *,
        travel_profile: str = "driving",
    ) -> FeasibilityVerdict:
        reasons: list[FeasibilityReason] = []

        self._check_active(experience, reasons)
        self._check_budget(experience, constraints, reasons)
        self._check_duration(experience, constraints, reasons)
        self._check_distance(experience, constraints, reasons)
        travel_time_minutes = await self._check_travel_time(
            experience, constraints, reasons, profile=travel_profile
        )
        self._check_total_time(experience, constraints, travel_time_minutes, reasons)
        self._check_opening_hours(experience, constraints, reasons)
        self._check_availability(experience, constraints, reasons)
        self._check_capacity(experience, constraints, reasons)
        self._check_accessibility(experience, constraints, reasons)
        self._check_itinerary_conflicts(experience, constraints, travel_time_minutes, reasons)

        has_unknown = any(r.code.name.endswith("UNAVAILABLE") or r.code in _UNKNOWN_CODES for r in reasons)
        has_infeasible = any(r.code not in _UNKNOWN_CODES and not r.code.name.endswith("UNAVAILABLE") for r in reasons)

        if reasons:
            status = "UNKNOWN" if has_unknown and not has_infeasible else "INFEASIBLE"
        else:
            status = "FEASIBLE"

        return FeasibilityVerdict(
            experience_id=experience.id,
            status=status,  # type: ignore[arg-type]
            reasons=reasons,
            checked_at=datetime.now(UTC),
            evidence={"travel_time_minutes": travel_time_minutes} if travel_time_minutes is not None else {},
        )

    # ─── individual checks ──────────────────────────────────────────────

    def _check_active(self, experience: Experience, reasons: list[FeasibilityReason]) -> None:
        if experience.status != "active":
            reasons.append(
                _reason(
                    FeasibilityReasonCode.EXPERIENCE_INACTIVE,
                    "active_status",
                    f"Experience status is '{experience.status}', not active.",
                    evidence={"status": experience.status},
                )
            )

    def _check_budget(
        self, experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if constraints.budget_max is None:
            return
        if constraints.currency.upper() != "INR" or experience.currency.upper() != "INR":
            reasons.append(
                _reason(
                    FeasibilityReasonCode.UNSUPPORTED_CURRENCY,
                    "budget",
                    "Currency conversion is not supported; budget check requires INR on both sides.",
                    evidence={"traveler_currency": constraints.currency, "experience_currency": experience.currency},
                )
            )
            return

        price = _effective_price(experience)
        if price is None:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.PRICE_UNAVAILABLE,
                    "budget",
                    "Experience has no stored price; cannot verify against the traveler's budget.",
                )
            )
            return

        if price > constraints.budget_max:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.BUDGET_EXCEEDED,
                    "budget",
                    f"Price {price} exceeds max budget {constraints.budget_max}.",
                    evidence={"price": price, "budget_max": constraints.budget_max},
                )
            )

    def _check_duration(
        self, experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if constraints.available_duration_minutes is None:
            return
        if experience.duration_minutes is None:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.DURATION_UNAVAILABLE,
                    "duration",
                    "Experience has no stored duration; cannot verify it fits the traveler's available time.",
                )
            )
            return
        if experience.duration_minutes > constraints.available_duration_minutes:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.DURATION_EXCEEDED,
                    "duration",
                    f"Duration {experience.duration_minutes}m exceeds available "
                    f"{constraints.available_duration_minutes}m.",
                    evidence={
                        "duration_minutes": experience.duration_minutes,
                        "available_duration_minutes": constraints.available_duration_minutes,
                    },
                )
            )

    def _check_distance(
        self, experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if constraints.max_distance_km is None:
            return
        if constraints.origin_lat is None or constraints.origin_lng is None:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.MISSING_ORIGIN,
                    "distance",
                    "A max distance was requested but no traveler origin was provided.",
                )
            )
            return
        distance_km = haversine_km(
            constraints.origin_lat, constraints.origin_lng, experience.location.latitude, experience.location.longitude
        )
        if distance_km > constraints.max_distance_km:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.MAX_DISTANCE_EXCEEDED,
                    "distance",
                    f"Distance {distance_km:.2f}km exceeds max {constraints.max_distance_km}km.",
                    evidence={"distance_km": round(distance_km, 2), "max_distance_km": constraints.max_distance_km},
                )
            )

    async def _check_travel_time(
        self,
        experience: Experience,
        constraints: TravelerConstraints,
        reasons: list[FeasibilityReason],
        *,
        profile: str,
    ) -> float | None:
        if constraints.max_travel_time_minutes is None:
            return None
        if constraints.origin_lat is None or constraints.origin_lng is None:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.MISSING_ORIGIN,
                    "travel_time",
                    "A max travel time was requested but no traveler origin was provided.",
                )
            )
            return None

        try:
            route = await self._routing.get_route(
                (constraints.origin_lat, constraints.origin_lng),
                (experience.location.latitude, experience.location.longitude),
                profile=constraints.travel_mode or profile,
            )
        except AdapterError:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.TRAVEL_TIME_UNAVAILABLE,
                    "travel_time",
                    "Routing service is unavailable; cannot verify travel time (hard constraint).",
                )
            )
            return None
        except ValueError:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.ROUTE_UNAVAILABLE,
                    "travel_time",
                    "Requested travel mode/profile is not supported by the routing service.",
                )
            )
            return None

        if route.duration_minutes > constraints.max_travel_time_minutes:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.TRAVEL_TIME_EXCEEDED,
                    "travel_time",
                    f"Travel time {route.duration_minutes:.1f}m exceeds max {constraints.max_travel_time_minutes}m.",
                    evidence={
                        "travel_time_minutes": route.duration_minutes,
                        "max_travel_time_minutes": constraints.max_travel_time_minutes,
                        "source": route.source,
                    },
                )
            )
        return route.duration_minutes

    def _check_total_time(
        self,
        experience: Experience,
        constraints: TravelerConstraints,
        travel_time_minutes: float | None,
        reasons: list[FeasibilityReason],
    ) -> None:
        if constraints.available_duration_minutes is None:
            return
        if travel_time_minutes is None or experience.duration_minutes is None:
            return  # already covered by DURATION_UNAVAILABLE / travel-time reasons above
        total = travel_time_minutes + experience.duration_minutes
        if total > constraints.available_duration_minutes:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.OUTSIDE_AVAILABLE_TIME,
                    "total_time",
                    f"Travel + experience time {total:.1f}m exceeds available "
                    f"{constraints.available_duration_minutes}m.",
                    evidence={
                        "travel_time_minutes": travel_time_minutes,
                        "duration_minutes": experience.duration_minutes,
                        "total_minutes": total,
                        "available_duration_minutes": constraints.available_duration_minutes,
                    },
                )
            )

    @staticmethod
    def _check_opening_hours(
        experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if constraints.available_date is None and constraints.available_start is None:
            return  # no time/date context given -> check not applicable

        tzname = constraints.timezone or experience.location.timezone or _DEFAULT_TZ
        try:
            ZoneInfo(tzname)
        except Exception:
            tzname = _DEFAULT_TZ

        if not experience.opening_hours:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.OPENING_HOURS_UNAVAILABLE,
                    "opening_hours",
                    "No opening hours are on record; cannot verify the experience is open at the requested time.",
                )
            )
            return

        target_date: date = constraints.available_date or datetime.now(ZoneInfo(tzname)).date()
        day_of_week = target_date.weekday()  # Monday=0 .. Sunday=6, matches stored convention
        prev_day_of_week = (day_of_week - 1) % 7

        # When the caller gave only a date (no specific start/end — e.g.
        # the itinerary composer's whole-day candidate gate, before any
        # per-item slot has been chosen), the question is "is this open at
        # all that day", not "is this open across the full synthetic
        # 00:00-23:59 day" — defaulting to a full-day window here would
        # make full CONTAINMENT require hours no real business has.
        # Precise-window callers (single-experience verification, and the
        # post-composition per-item re-check) keep the strict containment
        # semantics below.
        precise_window = constraints.available_start is not None
        start_t = constraints.available_start or time(0, 0)
        end_t = constraints.available_end or time(23, 59)

        def _minutes(t: time) -> int:
            return t.hour * 60 + t.minute

        req_start_min = _minutes(start_t)
        req_end_min = _minutes(end_t)

        todays_rows = [h for h in experience.opening_hours if h.day_of_week == day_of_week]
        prev_rows = [h for h in experience.opening_hours if h.day_of_week == prev_day_of_week]

        if not todays_rows and not prev_rows:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.OPENING_HOURS_UNAVAILABLE,
                    "opening_hours",
                    f"No opening-hours data for day_of_week={day_of_week}.",
                )
            )
            return

        if all(row.is_closed for row in todays_rows) and todays_rows:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.OPENING_HOURS_CONFLICT,
                    "opening_hours",
                    "Experience is closed on the requested day.",
                    evidence={"day_of_week": day_of_week},
                )
            )
            return

        def _satisfies(open_min: int, close_min: int, overnight: bool) -> bool:
            if precise_window:
                if overnight:
                    # today's window: [open_min, 1440)
                    return req_start_min >= open_min and req_end_min <= 1440
                return req_start_min >= open_min and req_end_min <= close_min
            # Overlap only: any part of the day's open hours intersects
            # any part of the requested day.
            if overnight:
                return True  # spans into tomorrow -> overlaps this day by definition
            return req_start_min < close_min and req_end_min > open_min

        covered = False
        for row in todays_rows:
            if row.is_closed or row.open_time is None or row.close_time is None:
                continue
            open_h, open_m_ = (int(x) for x in row.open_time.split(":"))
            close_h, close_m_ = (int(x) for x in row.close_time.split(":"))
            open_min, close_min = open_h * 60 + open_m_, close_h * 60 + close_m_
            overnight = close_min <= open_min
            if _satisfies(open_min, close_min, overnight):
                covered = True
                break

        if not covered and precise_window:
            # check yesterday's overnight window spilling into today: [0, close_min)
            for row in prev_rows:
                if row.is_closed or row.open_time is None or row.close_time is None:
                    continue
                open_h, open_m_ = (int(x) for x in row.open_time.split(":"))
                close_h, close_m_ = (int(x) for x in row.close_time.split(":"))
                open_min, close_min = open_h * 60 + open_m_, close_h * 60 + close_m_
                overnight = close_min <= open_min
                if overnight and req_start_min < close_min and req_end_min <= close_min:
                    covered = True
                    break

        if not covered:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.OPENING_HOURS_CONFLICT,
                    "opening_hours",
                    "Requested time window is outside the experience's opening hours.",
                    evidence={"day_of_week": day_of_week, "requested_start": str(start_t), "requested_end": str(end_t)},
                )
            )

    def _check_availability(
        self, experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if constraints.available_date is None and constraints.available_start is None:
            return

        # Callers (repository/pipeline) must eager-load `availability_slots`
        # before passing an Experience here — see ExperienceRepository
        # .get_by_id/.search which both selectinload it.
        availability_slots = experience.availability_slots
        if not availability_slots:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.AVAILABILITY_UNAVAILABLE,
                    "availability",
                    "No availability slots are on record; cannot verify a bookable slot exists.",
                )
            )
            return

        tzname = constraints.timezone or experience.location.timezone or _DEFAULT_TZ
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo(_DEFAULT_TZ)

        # Same precise-window-vs-date-only distinction as
        # _check_opening_hours: a date-only constraint (the itinerary
        # composer's whole-day candidate gate) means "is there any active
        # slot at all that day", not "is there a single slot spanning the
        # traveler's entire day" — defaulting to 00:00-23:59 containment
        # here would require an availability slot no venue realistically
        # has. Precise-window callers keep strict containment.
        precise_window = constraints.available_start is not None
        target_date = constraints.available_date
        start_t = constraints.available_start or time(0, 0)
        end_t = constraints.available_end or time(23, 59)

        window_start: datetime | None
        window_end: datetime | None
        if target_date is not None:
            window_start = datetime.combine(target_date, start_t, tzinfo=tz)
            window_end = datetime.combine(target_date, end_t, tzinfo=tz)
        else:
            window_start = window_end = None

        active_slots = [s for s in availability_slots if s.status == "active"]
        if not active_slots:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.AVAILABILITY_CONFLICT,
                    "availability",
                    "No active availability slots found.",
                )
            )
            return

        def _as_aware(value: datetime) -> datetime:
            # SQLite does not preserve tzinfo across a round trip even for
            # DateTime(timezone=True) columns (values come back naive);
            # PostgreSQL does. Treat a naive value as UTC (the documented
            # storage convention — see models/availability.py) rather than
            # erroring or silently miscomparing against an aware window.
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

        def _matches(slot_start: datetime, slot_end: datetime) -> bool:
            if window_start is None or window_end is None:
                return True
            aware_start, aware_end = _as_aware(slot_start), _as_aware(slot_end)
            if precise_window:
                return aware_start <= window_start and aware_end >= window_end
            return aware_start < window_end and aware_end > window_start

        if not any(_matches(s.starts_at, s.ends_at) for s in active_slots):
            reasons.append(
                _reason(
                    FeasibilityReasonCode.AVAILABILITY_CONFLICT,
                    "availability",
                    "No active availability slot contains the requested time window.",
                    evidence={
                        "requested_window": [str(window_start), str(window_end)] if window_start else None,
                    },
                )
            )

    def _check_capacity(
        self, experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if constraints.party_size is None:
            return
        capacity = experience.capacity if experience.capacity is not None else experience.maximum_group_size
        if capacity is None:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.CAPACITY_UNAVAILABLE,
                    "party_size",
                    "Experience has no stored capacity/group-size limit; cannot verify the party fits.",
                )
            )
            return
        if constraints.party_size > capacity:
            reasons.append(
                _reason(
                    FeasibilityReasonCode.GROUP_SIZE_EXCEEDS_CAPACITY,
                    "party_size",
                    f"Party size {constraints.party_size} exceeds capacity {capacity}.",
                    evidence={"party_size": constraints.party_size, "capacity": capacity},
                )
            )

    def _check_accessibility(
        self, experience: Experience, constraints: TravelerConstraints, reasons: list[FeasibilityReason]
    ) -> None:
        if not constraints.accessibility_requirements:
            return
        for requirement in constraints.accessibility_requirements:
            value = getattr(experience, requirement, None)
            if value is None:
                reasons.append(
                    _reason(
                        FeasibilityReasonCode.ACCESSIBILITY_DATA_UNAVAILABLE,
                        f"accessibility:{requirement}",
                        f"No stored data for accessibility requirement '{requirement}'.",
                    )
                )
            elif value is False:
                reasons.append(
                    _reason(
                        FeasibilityReasonCode.ACCESSIBILITY_NOT_SUPPORTED,
                        f"accessibility:{requirement}",
                        f"Experience does not support '{requirement}'.",
                        evidence={requirement: value},
                    )
                )

    def _check_itinerary_conflicts(
        self,
        experience: Experience,
        constraints: TravelerConstraints,
        travel_time_minutes: float | None,
        reasons: list[FeasibilityReason],
    ) -> None:
        if not constraints.existing_commitments:
            return
        if constraints.available_date is None or experience.duration_minutes is None:
            return  # no concrete anchor time to place the experience at -> not checkable

        tzname = constraints.timezone or experience.location.timezone or _DEFAULT_TZ
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo(_DEFAULT_TZ)

        start_t = constraints.available_start or time(0, 0)
        candidate_start = datetime.combine(constraints.available_date, start_t, tzinfo=tz)
        lead_in = timedelta(minutes=travel_time_minutes or 0)
        candidate_end = candidate_start + lead_in + timedelta(minutes=experience.duration_minutes)
        candidate_travel_start = candidate_start

        for block in constraints.existing_commitments:
            if candidate_travel_start < block.end and candidate_end > block.start:
                reasons.append(
                    _reason(
                        FeasibilityReasonCode.ITINERARY_CONFLICT,
                        "itinerary",
                        "Experience (including travel) overlaps an existing committed time block.",
                        evidence={
                            "candidate_start": str(candidate_travel_start),
                            "candidate_end": str(candidate_end),
                            "committed_start": str(block.start),
                            "committed_end": str(block.end),
                        },
                    )
                )
                break


_UNKNOWN_CODES = {
    FeasibilityReasonCode.PRICE_UNAVAILABLE,
    FeasibilityReasonCode.UNSUPPORTED_CURRENCY,
    FeasibilityReasonCode.DURATION_UNAVAILABLE,
    FeasibilityReasonCode.OPENING_HOURS_UNAVAILABLE,
    FeasibilityReasonCode.TRAVEL_TIME_UNAVAILABLE,
    FeasibilityReasonCode.MISSING_ORIGIN,
    FeasibilityReasonCode.ROUTE_UNAVAILABLE,
    FeasibilityReasonCode.CAPACITY_UNAVAILABLE,
    FeasibilityReasonCode.ACCESSIBILITY_DATA_UNAVAILABLE,
    FeasibilityReasonCode.AVAILABILITY_UNAVAILABLE,
    FeasibilityReasonCode.MISSING_TIME_CONTEXT,
    FeasibilityReasonCode.MISSING_LOCATION,
}


__all__ = ["FeasibilityService"]
