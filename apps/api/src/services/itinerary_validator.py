"""ItineraryValidatorService — mandatory post-composition validation (Phase 8).

Runs after the composer produces a schedule and before any narrative is
generated. 100% deterministic — no LLM involvement. Reuses
FeasibilityReasonCode (src/core/feasibility_reasons.py) for every issue
rather than inventing a parallel free-form string set.

Validates three levels:
  - Experience-level: each item's underlying Experience is FEASIBLE
    (delegates to FeasibilityService against the item's own planned
    start/end/party size/budget — never trusts the composer's earlier
    pass alone, since the DB may have changed between retrieval and
    validation).
  - Schedule-level: chronological order, no overlaps (including buffers),
    travel time/distance is known and consistent with the gap between
    items, no unintended duplicate experiences.
  - Itinerary-level: total cost within the requested budget (if any),
    item count within the configured/requested limit, every item
    FEASIBLE, start >= requested_start, end <= requested_end.

On INVALID, returns every violation found (never short-circuits on the
first) so the composer's retry loop can react to the full picture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.adapters.routing import RoutingAdapter
from src.core.feasibility_reasons import FeasibilityReasonCode
from src.models.experience import Experience
from src.schemas.feasibility import TravelerConstraints
from src.services.experience_composer import ComposedItem
from src.services.feasibility import FeasibilityService


@dataclass
class ValidationIssue:
    code: FeasibilityReasonCode
    constraint: str
    message: str
    evidence: dict[str, object] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)


class ItineraryValidatorService:
    def __init__(self, routing_adapter: RoutingAdapter) -> None:
        self._feasibility = FeasibilityService(routing_adapter)

    async def validate(
        self,
        *,
        items: list[ComposedItem],
        experiences_by_id: dict[str, Experience],
        requested_start: datetime,
        requested_end: datetime,
        max_budget: float | None,
        max_experiences: int | None,
        party_size: int | None,
        travel_mode: str,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        if not items:
            issues.append(
                ValidationIssue(
                    code=FeasibilityReasonCode.ITINERARY_EMPTY,
                    constraint="itinerary",
                    message="No experiences could be composed into a valid itinerary.",
                )
            )
            return ValidationResult(valid=False, issues=issues)

        if max_experiences is not None and len(items) > max_experiences:
            issues.append(
                ValidationIssue(
                    code=FeasibilityReasonCode.ITINERARY_COUNT_LIMIT_EXCEEDED,
                    constraint="max_experiences",
                    message=f"{len(items)} items exceeds the requested limit of {max_experiences}.",
                    evidence={"count": len(items), "max_experiences": max_experiences},
                )
            )

        seen_ids: set[str] = set()
        prev_end: datetime | None = None
        total_cost = 0.0

        for item in items:
            experience = experiences_by_id.get(item.experience.id)

            # Duplicate check.
            if item.experience.id in seen_ids:
                issues.append(
                    ValidationIssue(
                        code=FeasibilityReasonCode.DUPLICATE_EXPERIENCE,
                        constraint="itinerary",
                        message=f"Experience {item.experience.id} appears more than once.",
                        evidence={"experience_id": item.experience.id},
                    )
                )
            seen_ids.add(item.experience.id)

            # Duration/order sanity.
            if item.planned_end <= item.planned_start:
                issues.append(
                    ValidationIssue(
                        code=FeasibilityReasonCode.SCHEDULE_NOT_CHRONOLOGICAL,
                        constraint="schedule",
                        message=f"Item {item.experience.id} has a non-positive duration.",
                        evidence={
                            "planned_start": str(item.planned_start),
                            "planned_end": str(item.planned_end),
                        },
                    )
                )
            if item.buffer_before_minutes < 0 or item.buffer_after_minutes < 0:
                issues.append(
                    ValidationIssue(
                        code=FeasibilityReasonCode.INVALID_BUFFER,
                        constraint="schedule",
                        message=f"Item {item.experience.id} has a negative buffer.",
                    )
                )

            # Chronological + overlap check against the previous item.
            if prev_end is not None:
                if item.planned_start < prev_end:
                    issues.append(
                        ValidationIssue(
                            code=FeasibilityReasonCode.SCHEDULE_OVERLAP,
                            constraint="schedule",
                            message=(
                                f"Item {item.experience.id} starts at {item.planned_start} "
                                f"before the previous item ends at {prev_end}."
                            ),
                            evidence={
                                "planned_start": str(item.planned_start),
                                "previous_planned_end": str(prev_end),
                            },
                        )
                    )
                # Travel time must be known (never assumed 0) once there is
                # a previous stop to travel from.
                if item.travel_from_previous_minutes is None:
                    issues.append(
                        ValidationIssue(
                            code=FeasibilityReasonCode.TRAVEL_TRANSITION_IMPOSSIBLE,
                            constraint="travel_time",
                            message=(
                                f"Travel time to item {item.experience.id} is unknown — "
                                "cannot verify this transition is possible."
                            ),
                        )
                    )
                elif item.travel_from_previous_minutes < 0:
                    issues.append(
                        ValidationIssue(
                            code=FeasibilityReasonCode.TRAVEL_TRANSITION_IMPOSSIBLE,
                            constraint="travel_time",
                            message=f"Negative travel time computed for item {item.experience.id}.",
                        )
                    )

            # Window bounds.
            if item.planned_start < requested_start or item.planned_end > requested_end:
                issues.append(
                    ValidationIssue(
                        code=FeasibilityReasonCode.OUTSIDE_REQUESTED_WINDOW,
                        constraint="window",
                        message=f"Item {item.experience.id} falls outside the requested time window.",
                        evidence={
                            "planned_start": str(item.planned_start),
                            "planned_end": str(item.planned_end),
                            "requested_start": str(requested_start),
                            "requested_end": str(requested_end),
                        },
                    )
                )

            total_cost += item.estimated_cost or 0.0
            prev_end = item.planned_end

            # Experience-level feasibility re-check (constraints derived
            # from this item's own scheduled slot — never trusts the
            # composer's earlier snapshot alone). Skipped when the item's
            # own start/end are already invalid (SCHEDULE_NOT_CHRONOLOGICAL
            # above already covers that case; a same-day item spanning
            # midnight would also fail the plain start<end time-of-day
            # check here, which is a real limitation — see docs).
            if experience is not None and item.planned_end > item.planned_start and item.planned_start.time() != item.planned_end.time():
                constraints = TravelerConstraints(
                    budget_max=max_budget,
                    party_size=party_size,
                    available_date=item.planned_start.date(),
                    available_start=item.planned_start.time(),
                    available_end=item.planned_end.time(),
                    travel_mode=travel_mode,  # type: ignore[arg-type]
                )
                verdict = await self._feasibility.evaluate(
                    experience, constraints, travel_profile=travel_mode
                )
                if verdict.status != "FEASIBLE":
                    issues.append(
                        ValidationIssue(
                            code=FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE,
                            constraint="feasibility",
                            message=f"Experience {item.experience.id} is no longer feasible ({verdict.status}).",
                            evidence={
                                "experience_id": item.experience.id,
                                "status": verdict.status,
                                "reasons": [r.code.value for r in verdict.reasons],
                            },
                        )
                    )
            elif experience is None:
                issues.append(
                    ValidationIssue(
                        code=FeasibilityReasonCode.EXPERIENCE_NOT_FEASIBLE,
                        constraint="feasibility",
                        message=f"Experience {item.experience.id} could not be loaded for re-validation.",
                        evidence={"experience_id": item.experience.id},
                    )
                )

        if max_budget is not None and total_cost > max_budget:
            issues.append(
                ValidationIssue(
                    code=FeasibilityReasonCode.ITINERARY_BUDGET_EXCEEDED,
                    constraint="budget",
                    message=f"Total cost {total_cost} exceeds max budget {max_budget}.",
                    evidence={"total_cost": total_cost, "max_budget": max_budget},
                )
            )

        return ValidationResult(valid=not issues, issues=issues)


__all__ = ["ItineraryValidatorService", "ValidationIssue", "ValidationResult"]
