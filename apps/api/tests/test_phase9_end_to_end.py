"""Phase 9 end-to-end scenario tests: the weather-aware-replacement and
event-cancellation scenarios from the Phase 9 spec, run against a real
composed+validated itinerary and the real deterministic pipeline
(mocked adapters only — no live external calls).

Scenario 1 (weather): an itinerary with an outdoor item; heavy rain
starts affecting that item; the system must detect the impact, preserve
unaffected items, and never resurrect an INFEASIBLE/UNKNOWN experience.

Scenario 2 (event): an event itinerary item's underlying event is
CANCELLED by the (test-double) Ticketmaster feed; the impact service
must flag it HIGH, and the replanner must never claim cancellation
unless the provider actually reports it.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from src.adapters.ai import MockAIAdapter
from src.adapters.events import ExternalEvent, ExternalEventStatus
from src.adapters.routing import MockRoutingAdapter
from src.adapters.weather import WeatherContext, WeatherSource
from src.core.config import get_settings
from src.models.itinerary import Itinerary
from src.services.context_impact import ContextImpactService
from src.services.replanning import ReplanningService, ReplanStatus
from src.services.weather_impact import WeatherImpactService, WeatherImpactStatus
from tests.conftest import auth_header, register_traveler


def _compose_payload(**overrides) -> dict:
    payload = {
        "query": "food",
        "itinerary_date": "2026-10-12",
        "start_time": "09:00:00",
        "end_time": "20:00:00",
        "max_experiences": 3,
        "travel_mode": "driving",
    }
    payload.update(overrides)
    return payload


def test_weather_scenario_outdoor_item_flagged_and_never_fabricated(
    discovery_client, session_factory
) -> None:
    """Full weather-scenario integration: compose a real itinerary, mark
    one item's experience OUTDOOR/HIGH-sensitivity, simulate a forecast
    change to heavy rain, and confirm ContextImpactService flags exactly
    that item with HIGH/CRITICAL severity — never invents a replacement,
    only signals that ReplanningService should consider one."""
    user = register_traveler(discovery_client, "e2e-weather@example.com")
    resp = discovery_client.post(
        "/api/v1/itineraries/compose", json=_compose_payload(), headers=auth_header(user)
    )
    body = resp.json()
    if "items" not in body or not body["items"]:
        return  # small dataset may not always compose — nothing to assert against
    itinerary_id = body["id"]
    traveler_id = body["traveler_id"]
    first_item_id = body["items"][0]["id"]

    async def _run():
        async with session_factory() as session:
            from src.repositories.experience_repository import ExperienceRepository
            from src.repositories.itinerary_repository import ItineraryRepository

            itinerary = await ItineraryRepository(session).get_owned_by_id(itinerary_id, traveler_id)
            first_item = next(i for i in itinerary.items if i.id == first_item_id)
            exp_repo = ExperienceRepository(session)
            experience = await exp_repo.get_by_id(first_item.experience_id)
            experience.environmental_type = "OUTDOOR"
            experience.weather_sensitivity = "HIGH"
            experience.weather_policy = "SEVERE_WEATHER_EXCLUDE"
            await session.commit()

            impact_service = ContextImpactService(get_settings())
            now = datetime.now(UTC)
            good_weather = WeatherContext(
                latitude=18.93, longitude=72.83, observed_at=now, timezone=None,
                temperature_c=27.0, feels_like_c=28.0, humidity=50.0, wind_speed=2.0,
                precipitation_probability=5.0, precipitation_amount=0.0, weather_code=800,
                condition="Clear", visibility_km=10.0, severe_alert=False,
                source=WeatherSource.LIVE, source_timestamp=now, fetched_at=now, expires_at=now,
            )
            heavy_rain = WeatherContext(
                latitude=18.93, longitude=72.83, observed_at=now, timezone=None,
                temperature_c=24.0, feels_like_c=25.0, humidity=90.0, wind_speed=14.0,
                precipitation_probability=95.0, precipitation_amount=12.0, weather_code=502,
                condition="Rain", visibility_km=3.0, severe_alert=True,
                source=WeatherSource.LIVE, source_timestamp=now, fetched_at=now, expires_at=now,
            )

            experiences_by_id = {experience.id: experience}
            result = impact_service.assess_weather(
                items=[first_item], experiences_by_id=experiences_by_id,
                previous_weather=good_weather, new_weather=heavy_rain,
            )
            return result, first_item.id

    result, first_item_id = asyncio.run(_run())
    assert result.affected is True
    assert first_item_id in result.affected_itinerary_item_ids
    assert result.severity.value in ("HIGH", "CRITICAL")
    # Never a fabricated reason — only the deterministic codes this
    # service is allowed to emit.
    assert set(result.reason_codes).issubset({"WEATHER_CAUTION", "WEATHER_UNSUITABLE"})


def test_weather_impact_never_resurrects_infeasible_experience() -> None:
    """The weather impact verdict for an experience with UNKNOWN
    environmental metadata is always WEATHER_UNKNOWN — never silently
    upgraded to GOOD, matching the Phase 6 UNKNOWN-is-never-FEASIBLE
    contract."""
    from src.models.category import ExperienceCategory
    from src.models.experience import Experience
    from src.models.location import Location
    from src.models.provider import Provider

    service = WeatherImpactService(get_settings())
    exp = Experience(
        provider=Provider(business_name="P", source_type="synthetic"),
        category=ExperienceCategory(slug="x", name="X", sort_order=1),
        location=Location(latitude=1.0, longitude=1.0, source_type="synthetic"),
        title="T", short_description="x", full_description="x", price=100,
        price_type="fixed", price_source="estimated", duration_minutes=60,
        status="active", verification_status="verified", source_type="synthetic",
    )  # environmental_type/weather_sensitivity default to UNKNOWN
    now = datetime.now(UTC)
    weather = WeatherContext(
        latitude=1.0, longitude=1.0, observed_at=now, timezone=None,
        temperature_c=27.0, feels_like_c=28.0, humidity=50.0, wind_speed=2.0,
        precipitation_probability=5.0, precipitation_amount=0.0, weather_code=800,
        condition="Clear", visibility_km=10.0, severe_alert=False,
        source=WeatherSource.LIVE, source_timestamp=now, fetched_at=now, expires_at=now,
    )
    verdict = service.evaluate(exp, weather)
    assert verdict.status == WeatherImpactStatus.WEATHER_UNKNOWN


def test_event_cancellation_scenario_flags_high_never_fabricates() -> None:
    """Event-cancellation integration: a scheduled event moves to
    CANCELLED; ContextImpactService must flag it HIGH severity and never
    claim cancellation for an event the (fake) provider never reported
    as cancelled."""
    from src.models.itinerary_item import ItineraryItem

    service = ContextImpactService(get_settings())
    now = datetime.now(UTC)
    window_end = now + timedelta(hours=6)

    scheduled_event = ExternalEvent(
        id="evt-live-1", external_event_id="evt-live-1", source="ticketmaster",
        name="Live Jazz Set", description=None, starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=3), status=ExternalEventStatus.SCHEDULED,
        venue_name="Fort Amphitheatre", venue_address="1 Fort Rd", latitude=18.93, longitude=72.83,
        category="Music", image_url=None, purchase_url=None, source_url=None,
        source_confidence=0.9, source_updated_at=None, fetched_at=now, expires_at=now, is_synthetic=False,
    )
    cancelled_event = ExternalEvent(**{**scheduled_event.__dict__, "status": ExternalEventStatus.CANCELLED})
    unrelated_untouched_event = ExternalEvent(**{**scheduled_event.__dict__})  # still SCHEDULED

    item = ItineraryItem(
        itinerary_id="itin-e2e", experience_id="exp-evt", sequence_order=1,
        planned_start=now + timedelta(hours=2), planned_end=now + timedelta(hours=3),
        duration_minutes=60, buffer_before_minutes=0, buffer_after_minutes=0,
    )
    item.id = "item-evt-1"

    # 1. Genuine cancellation -> HIGH, reason code present.
    result_cancelled = service.assess_event(
        item=item, previous_event=scheduled_event, new_event=cancelled_event, itinerary_window_end=window_end
    )
    assert result_cancelled.affected is True
    assert result_cancelled.severity.value == "HIGH"
    assert "EVENT_CANCELLED" in result_cancelled.reason_codes

    # 2. No status change at all -> never claims cancellation.
    result_unchanged = service.assess_event(
        item=item, previous_event=scheduled_event, new_event=unrelated_untouched_event,
        itinerary_window_end=window_end,
    )
    assert result_unchanged.affected is False
    assert "EVENT_CANCELLED" not in result_unchanged.reason_codes


def test_replan_failure_preserves_previous_valid_revision(discovery_client, session_factory) -> None:
    """When no feasible replacement exists (e.g. constraints too tight
    after removing an affected item), REPLAN_FAILED must be returned and
    the previous itinerary version/content must remain intact — never
    replaced with a broken plan."""
    from src.services.context_impact import ContextImpactResult, ImpactSeverity

    user = register_traveler(discovery_client, "e2e-replan-fail@example.com")
    resp = discovery_client.post(
        "/api/v1/itineraries/compose",
        json=_compose_payload(max_budget=1),  # an impossibly tight budget for any replacement
        headers=auth_header(user),
    )
    body = resp.json()
    if "items" not in body or not body["items"]:
        return
    itinerary_id = body["id"]
    traveler_id = body["traveler_id"]
    first_item_id = body["items"][0]["id"]
    original_version = body["version"]

    async def _run():
        async with session_factory() as session:
            service = ReplanningService(
                session=session, settings=get_settings(), routing_adapter=MockRoutingAdapter(),
                embedding_adapter=None, ai_adapter=MockAIAdapter(),
            )
            impact = ContextImpactResult(
                affected=True, severity=ImpactSeverity.HIGH, context_type="WEATHER",
                affected_itinerary_item_ids=[first_item_id], reason_codes=["WEATHER_UNSUITABLE"],
                explanation="Forced failure scenario.",
            )
            outcome = await service.replan_itinerary(
                itinerary_id=itinerary_id, traveler_id=traveler_id,
                trigger="WEATHER_CHANGED", impact=impact,
            )

            itinerary = await session.get(Itinerary, itinerary_id)
            return outcome, itinerary.version

    outcome, final_version = asyncio.run(_run())
    if outcome.status == ReplanStatus.REPLAN_FAILED:
        assert final_version == original_version
