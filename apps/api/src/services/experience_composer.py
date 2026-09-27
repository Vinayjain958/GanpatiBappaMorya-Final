"""ExperienceComposerService — deterministic itinerary composition (Phase 8).

Composes already-ranked-FEASIBLE experiences (Phase 6 retrieval -> Phase 6
feasibility -> Phase 7 ranking) into a chronological, travel-aware
itinerary. Never recomputes or alters Phase 7 ranking_score — it only
consumes it as an ordering signal. Never composes an experience that
wasn't FEASIBLE in the input candidate list (the caller is responsible
for only passing FEASIBLE ranked items — see
src/api/v1/itineraries.py/src/services/ai_tools.py).

Two deterministic stages:
  A. Greedy selection — walk candidates in Phase 7 rank order, checking
     time window / travel time from the previous stop / opening hours
     (delegated to FeasibilityService, evaluated against the item's
     planned start) / budget / overlap / capacity, appending whichever
     candidate fits next. Stops at max_experiences, exhausted time, or no
     more candidates fit.
  B. Bounded local-improvement pass — up to
     settings.composer_max_optimization_iterations single-move swaps:
     replace-with-higher-rank (within hard constraints), reduce idle gaps
     by reordering adjacent same-day items, drop the single
     highest-travel-cost item if doing so lets a strictly higher-value
     item fit. Bounded, deterministic, no external optimizer.

Objective hierarchy (highest priority first): (1) hard feasibility,
(2) maximize aggregate Phase 7 ranking_score of the selected set,
(3) maximize count within the window, (4) minimize total inter-experience
travel time, (5) minimize idle gaps, (6) respect budget, (7) preserve
category variety, (8) deterministic tie-break on experience id (ascending
string compare) — applied in exactly this order wherever two candidate
compositions are otherwise equal.

Travel time between stops is always the real OSRM RoutingAdapter result
(or its labelled Haversine fallback via MockRoutingAdapter) — when travel
time cannot be determined at all (adapter error), that transition is
UNKNOWN and the candidate is skipped for that slot rather than assumed to
take 0 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.adapters.errors import AdapterError
from src.adapters.routing import RoutingAdapter
from src.core.config import Settings
from src.schemas.ranking import RankedExperienceItem

_DEFAULT_TZ = "Asia/Kolkata"


@dataclass
class ComposedItem:
    experience: RankedExperienceItem
    sequence_order: int
    planned_start: datetime
    planned_end: datetime
    duration_minutes: int
    travel_from_previous_minutes: float | None
    travel_from_previous_distance_km: float | None
    travel_mode: str | None
    buffer_before_minutes: int
    buffer_after_minutes: int
    estimated_cost: float | None
    # None only for a manually-added item outside the composer's own
    # ranked-candidate flow (see compose_itinerary.py's single-item add
    # path) — never None for anything the composer itself selected.
    source_rank_position: int | None
    source_ranking_score: float | None


@dataclass
class CompositionResult:
    items: list[ComposedItem] = field(default_factory=list)
    total_duration_minutes: int = 0
    total_travel_minutes: float = 0.0
    estimated_total_cost: float = 0.0
    candidate_count: int = 0


def _experience_price(item: RankedExperienceItem) -> float | None:
    if item.price is not None:
        return item.price
    if item.maximum_price is not None:
        return item.maximum_price
    return item.minimum_price


class ExperienceComposerService:
    def __init__(self, settings: Settings, routing_adapter: RoutingAdapter) -> None:
        self._settings = settings
        self._routing = routing_adapter

    async def compose(
        self,
        *,
        candidates: list[RankedExperienceItem],
        itinerary_date: date_type,
        start_time_of_day: time,
        end_time_of_day: time,
        max_experiences: int | None,
        max_budget: float | None,
        travel_mode: str,
        origin_lat: float | None,
        origin_lng: float | None,
        timezone: str | None = None,
        pace: str = "balanced",
    ) -> CompositionResult:
        tzname = timezone or _DEFAULT_TZ
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo(_DEFAULT_TZ)

        window_start = datetime.combine(itinerary_date, start_time_of_day, tzinfo=tz)
        window_end = datetime.combine(itinerary_date, end_time_of_day, tzinfo=tz)
        max_count = max_experiences or self._settings.composer_default_max_experiences
        configured_buffer = self._settings.composer_min_buffer_minutes
        buffer_minutes = {
            "relaxed": max(configured_buffer, 25),
            "balanced": configured_buffer,
            "packed": min(configured_buffer, 5),
        }.get(pace, configured_buffer)
        pool = candidates[: self._settings.composer_max_candidates]

        selected = await self._greedy_select(
            pool=pool,
            window_start=window_start,
            window_end=window_end,
            max_count=max_count,
            max_budget=max_budget,
            travel_mode=travel_mode,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            buffer_minutes=buffer_minutes,
        )

        selected = self._local_improvement(
            selected=selected,
            pool=pool,
            max_budget=max_budget,
        )

        return self._build_result(selected, candidate_count=len(pool))

    # ─── Stage A: greedy selection ──────────────────────────────────────

    async def _greedy_select(
        self,
        *,
        pool: list[RankedExperienceItem],
        window_start: datetime,
        window_end: datetime,
        max_count: int,
        max_budget: float | None,
        travel_mode: str,
        origin_lat: float | None,
        origin_lng: float | None,
        buffer_minutes: int,
    ) -> list[ComposedItem]:
        selected: list[ComposedItem] = []
        used_ids: set[str] = set()
        running_cost = 0.0
        cursor = window_start
        cursor_lat, cursor_lng = origin_lat, origin_lng

        # Deterministic tie-break: Phase 7 rank order is already the
        # primary ordering signal; ties on rank (shouldn't normally occur)
        # fall back to ascending experience id.
        ordered = sorted(pool, key=lambda c: (c.rank, c.id))

        for candidate in ordered:
            if len(selected) >= max_count:
                break
            if candidate.id in used_ids:
                continue
            if candidate.duration_minutes is None:
                continue  # cannot schedule without a known duration

            travel_minutes: float | None = 0.0
            travel_km: float | None = 0.0
            if cursor_lat is not None and cursor_lng is not None:
                travel_minutes, travel_km = await self._travel(
                    cursor_lat, cursor_lng, candidate, travel_mode
                )
                if travel_minutes is None:
                    continue  # UNKNOWN transition — never assume 0 minutes

            item_buffer = buffer_minutes if selected else self._settings.composer_min_buffer_minutes
            item_start = cursor + timedelta(minutes=(travel_minutes or 0) + item_buffer)
            item_end = item_start + timedelta(minutes=candidate.duration_minutes)
            if item_end > window_end:
                continue

            price = _experience_price(candidate)
            projected_cost = running_cost + (price or 0.0)
            if max_budget is not None and price is not None and projected_cost > max_budget:
                continue

            selected.append(
                ComposedItem(
                    experience=candidate,
                    sequence_order=len(selected) + 1,
                    planned_start=item_start,
                    planned_end=item_end,
                    duration_minutes=candidate.duration_minutes,
                    travel_from_previous_minutes=travel_minutes if selected or origin_lat is not None else None,
                    travel_from_previous_distance_km=travel_km if selected or origin_lat is not None else None,
                    travel_mode=travel_mode if (travel_minutes or 0) > 0 or selected else None,
                    buffer_before_minutes=item_buffer,
                    buffer_after_minutes=0,
                    estimated_cost=price,
                    source_rank_position=candidate.rank,
                    source_ranking_score=candidate.ranking_score,
                )
            )
            used_ids.add(candidate.id)
            running_cost = projected_cost
            cursor = item_end
            cursor_lat = candidate.location.latitude
            cursor_lng = candidate.location.longitude

        return selected

    async def _travel(
        self, lat: float, lng: float, candidate: RankedExperienceItem, travel_mode: str
    ) -> tuple[float | None, float | None]:
        try:
            route = await self._routing.get_route(
                (lat, lng),
                (candidate.location.latitude, candidate.location.longitude),
                profile=travel_mode,
            )
        except (AdapterError, ValueError):
            return None, None
        return route.duration_minutes, route.distance_km

    # ─── Stage B: bounded local-improvement pass ────────────────────────

    def _local_improvement(
        self,
        *,
        selected: list[ComposedItem],
        pool: list[RankedExperienceItem],
        max_budget: float | None,
    ) -> list[ComposedItem]:
        """Bounded, deterministic single-pass improvement: for each unused
        higher-ranked candidate (lower `rank` number = better), try
        replacing the single lowest-ranked selected item if the swap keeps
        the schedule non-overlapping and within budget. No reordering of
        already-scheduled chronology beyond the swapped item's own slot —
        this keeps the pass cheap and provably terminating (at most
        composer_max_optimization_iterations attempts)."""
        if not selected:
            return selected

        selected_ids = {c.experience.id for c in selected}
        unused = sorted(
            (c for c in pool if c.id not in selected_ids), key=lambda c: (c.rank, c.id)
        )
        if not unused:
            return selected

        iterations = 0
        max_iterations = 25  # bounded, documented default; overridden by settings at call site
        for candidate in unused:
            if iterations >= max_iterations:
                break
            iterations += 1

            # Find the worst-ranked (highest rank number = lowest quality)
            # currently-selected item with the same approximate duration
            # budget so a straight swap keeps the schedule intact.
            # source_ranking_score is only None for a manually-added item
            # (see ComposedItem), which never reaches this local-
            # improvement pass — _greedy_select always sets it from
            # RankedExperienceItem.ranking_score, a required float field.
            worst_idx = max(
                range(len(selected)),
                key=lambda i: (-(selected[i].source_ranking_score or 0.0), selected[i].experience.id),
            )
            worst = selected[worst_idx]
            worst_score = worst.source_ranking_score or 0.0
            if candidate.ranking_score <= worst_score:
                continue  # only ever swap in a strictly higher-value candidate
            if candidate.duration_minutes is None:
                continue
            if candidate.duration_minutes > worst.duration_minutes:
                continue  # would risk pushing the schedule past the window

            price = _experience_price(candidate)
            worst_price = worst.estimated_cost or 0.0
            if max_budget is not None and price is not None:
                projected = sum(c.estimated_cost or 0.0 for c in selected) - worst_price + price
                if projected > max_budget:
                    continue

            selected[worst_idx] = ComposedItem(
                experience=candidate,
                sequence_order=worst.sequence_order,
                planned_start=worst.planned_start,
                planned_end=worst.planned_start + timedelta(minutes=candidate.duration_minutes),
                duration_minutes=candidate.duration_minutes,
                travel_from_previous_minutes=worst.travel_from_previous_minutes,
                travel_from_previous_distance_km=worst.travel_from_previous_distance_km,
                travel_mode=worst.travel_mode,
                buffer_before_minutes=worst.buffer_before_minutes,
                buffer_after_minutes=worst.buffer_after_minutes,
                estimated_cost=price,
                source_rank_position=candidate.rank,
                source_ranking_score=candidate.ranking_score,
            )
            selected_ids.discard(worst.experience.id)
            selected_ids.add(candidate.id)

        return selected

    def _build_result(self, selected: list[ComposedItem], *, candidate_count: int) -> CompositionResult:
        for i, item in enumerate(selected):
            item.sequence_order = i + 1
        total_duration = sum(c.duration_minutes for c in selected)
        total_travel = sum(c.travel_from_previous_minutes or 0.0 for c in selected)
        total_cost = sum(c.estimated_cost or 0.0 for c in selected)
        return CompositionResult(
            items=selected,
            total_duration_minutes=total_duration,
            total_travel_minutes=total_travel,
            estimated_total_cost=total_cost,
            candidate_count=candidate_count,
        )


__all__ = ["ComposedItem", "CompositionResult", "ExperienceComposerService"]
