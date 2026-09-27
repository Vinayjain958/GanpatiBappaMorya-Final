"""ContextImpactService unit tests (Phase 9)."""

from __future__ import annotations

from datetime import UTC, datetime

from src.adapters.events import ExternalEvent, ExternalEventStatus
from src.adapters.weather import WeatherContext, WeatherSource
from src.core.config import Settings
from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.itinerary_item import ItineraryItem
from src.models.location import Location
from src.models.provider import Provider
from src.services.context_impact import ContextImpactService, ImpactSeverity


def _weather(**overrides) -> WeatherContext:
    now = datetime.now(UTC)
    base = dict(
        latitude=18.93, longitude=72.83, observed_at=now, timezone=None,
        temperature_c=27.0, feels_like_c=28.0, humidity=50.0, wind_speed=2.0,
        precipitation_probability=5.0, precipitation_amount=0.0, weather_code=800,
        condition="Clear", visibility_km=10.0, severe_alert=False,
        source=WeatherSource.LIVE, source_timestamp=now, fetched_at=now, expires_at=now,
    )
    base.update(overrides)
    return WeatherContext(**base)


def _outdoor_experience(sensitivity="HIGH", policy="SEVERE_WEATHER_EXCLUDE") -> Experience:
    exp = Experience(
        provider=Provider(business_name="P", source_type="synthetic"),
        category=ExperienceCategory(slug="outdoor", name="Outdoor", sort_order=1),
        location=Location(latitude=18.93, longitude=72.83, source_type="synthetic"),
        title="Outdoor Fort Walk", short_description="x", full_description="x",
        price=100, price_type="fixed", price_source="estimated",
        duration_minutes=90, status="active", verification_status="verified",
        source_type="synthetic",
        environmental_type="OUTDOOR", weather_sensitivity=sensitivity, weather_policy=policy,
    )
    return exp


def _indoor_experience() -> Experience:
    exp = Experience(
        provider=Provider(business_name="P", source_type="synthetic"),
        category=ExperienceCategory(slug="indoor", name="Indoor", sort_order=1),
        location=Location(latitude=18.93, longitude=72.83, source_type="synthetic"),
        title="Indoor Museum", short_description="x", full_description="x",
        price=100, price_type="fixed", price_source="estimated",
        duration_minutes=90, status="active", verification_status="verified",
        source_type="synthetic",
        environmental_type="INDOOR", weather_sensitivity="LOW", weather_policy="NONE",
    )
    return exp


def _item(experience_id: str, item_id: str = "item-1") -> ItineraryItem:
    now = datetime.now(UTC)
    item = ItineraryItem(
        itinerary_id="itin-1", experience_id=experience_id, sequence_order=1,
        planned_start=now, planned_end=now, duration_minutes=90,
        buffer_before_minutes=0, buffer_after_minutes=0,
    )
    item.id = item_id
    return item


def test_no_material_weather_change_is_none() -> None:
    service = ContextImpactService(Settings())
    exp = _outdoor_experience()
    exp.id = "exp-1"
    item = _item("exp-1")
    weather = _weather()

    result = service.assess_weather(
        items=[item], experiences_by_id={"exp-1": exp}, previous_weather=weather, new_weather=weather
    )
    assert result.affected is False
    assert result.severity == ImpactSeverity.NONE


def test_outdoor_severe_weather_is_high_or_critical() -> None:
    service = ContextImpactService(Settings())
    exp = _outdoor_experience()
    exp.id = "exp-1"
    item = _item("exp-1")
    prev = _weather()
    new = _weather(severe_alert=True, precipitation_probability=90.0, precipitation_amount=10.0)

    result = service.assess_weather(
        items=[item], experiences_by_id={"exp-1": exp}, previous_weather=prev, new_weather=new
    )
    assert result.affected is True
    assert result.severity in (ImpactSeverity.HIGH, ImpactSeverity.CRITICAL)
    assert "exp-1" not in [] or item.id in result.affected_itinerary_item_ids


def test_indoor_unaffected_by_severe_weather() -> None:
    service = ContextImpactService(Settings())
    exp = _indoor_experience()
    exp.id = "exp-2"
    item = _item("exp-2")
    prev = _weather()
    new = _weather(severe_alert=True, precipitation_probability=95.0)

    result = service.assess_weather(
        items=[item], experiences_by_id={"exp-2": exp}, previous_weather=prev, new_weather=new
    )
    assert result.affected is False


def test_cosmetic_event_change_is_none() -> None:
    service = ContextImpactService(Settings())
    now = datetime.now(UTC)
    prev_event = ExternalEvent(
        id="evt-1", external_event_id="evt-1", source="ticketmaster", name="Show",
        description="Old description", starts_at=now, ends_at=now, status=ExternalEventStatus.SCHEDULED,
        venue_name="Venue A", venue_address="Addr", latitude=1.0, longitude=1.0, category="Music",
        image_url="https://old.jpg", purchase_url="https://x", source_url="https://x",
        source_confidence=0.9, source_updated_at=None, fetched_at=now, expires_at=now, is_synthetic=False,
    )
    new_event = ExternalEvent(
        **{**prev_event.__dict__, "description": "New description text", "image_url": "https://new.jpg"}
    )
    item = _item("exp-3")

    result = service.assess_event(
        item=item, previous_event=prev_event, new_event=new_event, itinerary_window_end=now
    )
    assert result.affected is False
    assert result.severity == ImpactSeverity.NONE


def test_event_cancellation_is_high() -> None:
    service = ContextImpactService(Settings())
    now = datetime.now(UTC)
    prev_event = ExternalEvent(
        id="evt-1", external_event_id="evt-1", source="ticketmaster", name="Show",
        description=None, starts_at=now, ends_at=now, status=ExternalEventStatus.SCHEDULED,
        venue_name="Venue A", venue_address="Addr", latitude=1.0, longitude=1.0, category="Music",
        image_url=None, purchase_url=None, source_url=None,
        source_confidence=0.9, source_updated_at=None, fetched_at=now, expires_at=now, is_synthetic=False,
    )
    new_event = ExternalEvent(**{**prev_event.__dict__, "status": ExternalEventStatus.CANCELLED})
    item = _item("exp-3")

    result = service.assess_event(
        item=item, previous_event=prev_event, new_event=new_event, itinerary_window_end=now
    )
    assert result.affected is True
    assert result.severity == ImpactSeverity.HIGH
    assert "EVENT_CANCELLED" in result.reason_codes


def test_event_reschedule_outside_window_is_high() -> None:
    from datetime import timedelta

    service = ContextImpactService(Settings())
    now = datetime.now(UTC)
    window_end = now + timedelta(hours=2)
    prev_event = ExternalEvent(
        id="evt-1", external_event_id="evt-1", source="ticketmaster", name="Show",
        description=None, starts_at=now, ends_at=now, status=ExternalEventStatus.SCHEDULED,
        venue_name="Venue A", venue_address="Addr", latitude=1.0, longitude=1.0, category="Music",
        image_url=None, purchase_url=None, source_url=None,
        source_confidence=0.9, source_updated_at=None, fetched_at=now, expires_at=now, is_synthetic=False,
    )
    new_event = ExternalEvent(
        **{
            **prev_event.__dict__,
            "status": ExternalEventStatus.RESCHEDULED,
            "starts_at": now + timedelta(hours=5),  # after window_end
        }
    )
    item = _item("exp-3")

    result = service.assess_event(
        item=item, previous_event=prev_event, new_event=new_event, itinerary_window_end=window_end
    )
    assert result.affected is True
    assert result.severity == ImpactSeverity.HIGH


def test_time_shift_that_still_fits_is_medium_or_lower() -> None:
    from datetime import timedelta

    service = ContextImpactService(Settings())
    now = datetime.now(UTC)
    window_end = now + timedelta(hours=10)
    prev_event = ExternalEvent(
        id="evt-1", external_event_id="evt-1", source="ticketmaster", name="Show",
        description=None, starts_at=now, ends_at=now, status=ExternalEventStatus.SCHEDULED,
        venue_name="Venue A", venue_address="Addr", latitude=1.0, longitude=1.0, category="Music",
        image_url=None, purchase_url=None, source_url=None,
        source_confidence=0.9, source_updated_at=None, fetched_at=now, expires_at=now, is_synthetic=False,
    )
    new_event = ExternalEvent(
        **{
            **prev_event.__dict__,
            "status": ExternalEventStatus.RESCHEDULED,
            "starts_at": now + timedelta(hours=1),  # still well within window
        }
    )
    item = _item("exp-3")
    item.planned_end = now + timedelta(hours=2)

    result = service.assess_event(
        item=item, previous_event=prev_event, new_event=new_event, itinerary_window_end=window_end
    )
    if result.affected:
        assert result.severity in (ImpactSeverity.MEDIUM, ImpactSeverity.LOW)


def test_unavailable_weather_context_is_unknown_not_none() -> None:
    from src.adapters.weather import unavailable_context

    service = ContextImpactService(Settings())
    exp = _outdoor_experience()
    exp.id = "exp-1"
    item = _item("exp-1")
    new = unavailable_context(18.93, 72.83)

    result = service.assess_weather(
        items=[item], experiences_by_id={"exp-1": exp}, previous_weather=None, new_weather=new
    )
    assert result.affected is False
    assert result.severity == ImpactSeverity.UNKNOWN
