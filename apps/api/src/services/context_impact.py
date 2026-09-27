"""ContextImpactService — deterministic context-change-impact detection (Phase 9).

Compares previous vs new context (weather or events) against an
itinerary's remaining items and produces a ContextImpactResult:
affected, severity, affected_itinerary_item_ids, reason_codes,
explanation. Severity only signals whether ReplanningService should
CONSIDER replanning — it never itself reorders or mutates anything.

Weather triggers (see docs/AI_CONTEXT.md / Phase 9 spec): an outdoor
item's WeatherImpactService verdict crosses from
GOOD/CAUTION -> UNSUITABLE (material), a severe alert appears, material
precipitation change during the planned window. NOT every temperature
tick — small changes below configured thresholds plus a hysteresis band
never flip status.

Event triggers: CANCELLED, POSTPONED, RESCHEDULED outside the
itinerary's window, a start-time move creating a schedule conflict,
authoritative unavailability. NOT cosmetic metadata/image/description
changes — those are explicitly ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.adapters.events import ExternalEvent, ExternalEventStatus
from src.adapters.weather import WeatherContext, WeatherSource
from src.core.config import Settings
from src.models.experience import Experience
from src.models.itinerary_item import ItineraryItem
from src.services.weather_impact import WeatherImpactService, WeatherImpactStatus


class ImpactSeverity(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class ContextImpactResult:
    affected: bool
    severity: ImpactSeverity
    context_type: str  # "WEATHER" | "EVENTS" | "USER"
    affected_itinerary_item_ids: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    explanation: str = ""
    previous_context_reference: str | None = None
    new_context_reference: str | None = None


_STATUS_RANK = {
    WeatherImpactStatus.WEATHER_GOOD: 0,
    WeatherImpactStatus.WEATHER_CAUTION: 1,
    WeatherImpactStatus.WEATHER_UNSUITABLE: 2,
    WeatherImpactStatus.WEATHER_UNKNOWN: -1,
}


class ContextImpactService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._weather_impact = WeatherImpactService(settings)

    def assess_weather(
        self,
        *,
        items: list[ItineraryItem],
        experiences_by_id: dict[str, Experience],
        previous_weather: WeatherContext | None,
        new_weather: WeatherContext,
    ) -> ContextImpactResult:
        if new_weather.source == WeatherSource.UNAVAILABLE:
            return ContextImpactResult(
                affected=False,
                severity=ImpactSeverity.UNKNOWN,
                context_type="WEATHER",
                explanation="New weather context is unavailable — no auto-replan triggered.",
            )

        affected_ids: list[str] = []
        reason_codes: list[str] = []
        max_severity = ImpactSeverity.NONE

        for item in items:
            experience = experiences_by_id.get(item.experience_id)
            if experience is None:
                continue

            new_verdict = self._weather_impact.evaluate(experience, new_weather)

            if previous_weather is not None and previous_weather.source != WeatherSource.UNAVAILABLE:
                prev_verdict = self._weather_impact.evaluate(experience, previous_weather)
            else:
                prev_verdict = None

            if new_verdict.status == WeatherImpactStatus.WEATHER_UNKNOWN:
                continue  # never trigger a replan off UNKNOWN

            new_rank = _STATUS_RANK[new_verdict.status]
            prev_rank = _STATUS_RANK[prev_verdict.status] if prev_verdict else -1

            # Hysteresis: only treat as a material change when the new
            # verdict is strictly worse than before (or this is the first
            # assessment and it's already CAUTION/UNSUITABLE) — a
            # GOOD->CAUTION->GOOD flap within one cycle never fires twice
            # because we compare against the last known verdict, not a
            # raw threshold each time.
            if prev_verdict is not None and new_rank <= prev_rank:
                continue
            if prev_verdict is None and new_verdict.status == WeatherImpactStatus.WEATHER_GOOD:
                continue

            affected_ids.append(item.id)
            if new_verdict.status == WeatherImpactStatus.WEATHER_UNSUITABLE:
                reason_codes.append("WEATHER_UNSUITABLE")
                severity = ImpactSeverity.CRITICAL if new_weather.severe_alert else ImpactSeverity.HIGH
            else:
                reason_codes.append("WEATHER_CAUTION")
                severity = ImpactSeverity.MEDIUM

            if _SEVERITY_RANK[severity] > _SEVERITY_RANK[max_severity]:
                max_severity = severity

        affected = bool(affected_ids)
        explanation = (
            f"{len(affected_ids)} item(s) affected by a weather condition change."
            if affected
            else "No material weather impact on the remaining itinerary."
        )
        return ContextImpactResult(
            affected=affected,
            severity=max_severity if affected else ImpactSeverity.NONE,
            context_type="WEATHER",
            affected_itinerary_item_ids=affected_ids,
            reason_codes=sorted(set(reason_codes)),
            explanation=explanation,
        )

    def assess_event(
        self,
        *,
        item: ItineraryItem,
        previous_event: ExternalEvent | None,
        new_event: ExternalEvent,
        itinerary_window_end: datetime,
    ) -> ContextImpactResult:
        reason_codes: list[str] = []
        severity = ImpactSeverity.NONE

        if new_event.status == ExternalEventStatus.CANCELLED and (
            previous_event is None or previous_event.status != ExternalEventStatus.CANCELLED
        ):
            reason_codes.append("EVENT_CANCELLED")
            severity = ImpactSeverity.HIGH
        elif new_event.status == ExternalEventStatus.POSTPONED and (
            previous_event is None or previous_event.status != ExternalEventStatus.POSTPONED
        ):
            reason_codes.append("EVENT_POSTPONED")
            severity = ImpactSeverity.HIGH
        elif (
            new_event.status == ExternalEventStatus.RESCHEDULED
            and new_event.starts_at is not None
            and (previous_event is None or previous_event.starts_at != new_event.starts_at)
        ):
            if new_event.starts_at > itinerary_window_end:
                reason_codes.append("EVENT_RESCHEDULED")
                severity = ImpactSeverity.HIGH
            else:
                reason_codes.append("EVENT_RESCHEDULED")
                severity = ImpactSeverity.MEDIUM
        elif (
            previous_event is not None
            and previous_event.starts_at is not None
            and new_event.starts_at is not None
            and previous_event.starts_at != new_event.starts_at
        ):
            # Plain start-time move (no explicit reschedule status) that
            # creates a conflict with the itinerary window.
            if new_event.starts_at > itinerary_window_end or item.planned_end < new_event.starts_at:
                reason_codes.append("EVENT_VENUE_CHANGED" if previous_event.venue_name != new_event.venue_name else "TIME_CHANGED")
                severity = ImpactSeverity.MEDIUM
        elif (
            previous_event is not None
            and previous_event.venue_name != new_event.venue_name
            and (previous_event.latitude, previous_event.longitude) != (new_event.latitude, new_event.longitude)
        ):
            reason_codes.append("EVENT_VENUE_CHANGED")
            severity = ImpactSeverity.MEDIUM
        # Cosmetic changes (description/image_url/purchase_url) are
        # deliberately never checked here — never a replan trigger.

        affected = bool(reason_codes)
        explanation = (
            f"Event '{new_event.name}' changed: {', '.join(reason_codes)}."
            if affected
            else "No material event impact detected (cosmetic change only, if any)."
        )
        return ContextImpactResult(
            affected=affected,
            severity=severity if affected else ImpactSeverity.NONE,
            context_type="EVENTS",
            affected_itinerary_item_ids=[item.id] if affected else [],
            reason_codes=reason_codes,
            explanation=explanation,
        )


_SEVERITY_RANK = {
    ImpactSeverity.NONE: 0,
    ImpactSeverity.LOW: 1,
    ImpactSeverity.MEDIUM: 2,
    ImpactSeverity.HIGH: 3,
    ImpactSeverity.CRITICAL: 4,
    ImpactSeverity.UNKNOWN: -1,
}


__all__ = ["ContextImpactResult", "ContextImpactService", "ImpactSeverity"]
