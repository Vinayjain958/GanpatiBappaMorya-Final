"""Development-only weather scenario tests; no OpenWeather calls or writes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.adapters.weather import WeatherContext, WeatherSource
from src.adapters.weather_scenarios import WeatherScenario, build_weather_scenario
from src.core.config import Settings, get_settings
from src.core.context import get_weather_adapter
from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.itinerary_item import ItineraryItem
from src.models.location import Location
from src.models.provider import Provider
from src.services.context_impact import ContextImpactService
from src.services.weather_impact import WeatherImpactService, WeatherImpactStatus
from tests.conftest import auth_header, register_traveler

EXPECTED = {
    "SCENARIO_CLEAR": (28, 30, 60, 2, 0, 0, 800, "Clear", False, WeatherImpactStatus.WEATHER_GOOD),
    "SCENARIO_RAIN": (26, 27, 90, 4, 90, 8, 500, "Rain", False, WeatherImpactStatus.WEATHER_UNSUITABLE),
    "SCENARIO_STORM": (
        24,
        25,
        95,
        15,
        100,
        20,
        200,
        "Thunderstorm",
        True,
        WeatherImpactStatus.WEATHER_UNSUITABLE,
    ),
    "SCENARIO_HEAT": (40, 45, 70, 2, 0, 0, 800, "Clear", False, WeatherImpactStatus.WEATHER_UNSUITABLE),
}


class NoCallWeatherAdapter:
    async def get_current(self, lat: float, lng: float) -> WeatherContext:
        raise AssertionError("scenario test must not call the configured weather adapter")

    async def get_forecast(self, lat: float, lng: float) -> list[WeatherContext]:
        raise AssertionError("scenario test must not call the configured weather adapter")


@pytest.mark.parametrize("scenario", list(EXPECTED))
def test_weather_api_returns_temporary_mock_scenario(client: TestClient, scenario: WeatherScenario) -> None:
    traveler = register_traveler(client, f"weather-{scenario.lower()}@example.com")
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_weather_adapter] = lambda: NoCallWeatherAdapter()
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="development", openweather_api_key="configured-but-never-used"
    )
    headers = auth_header(traveler)

    current = client.get(
        f"/api/v1/context/weather?lat=18.93&lng=72.83&scenario={scenario}", headers=headers
    )
    assert current.status_code == 200, current.text
    body = current.json()
    values = EXPECTED[scenario]
    assert (
        body["temperature_c"],
        body["feels_like_c"],
        body["humidity"],
        body["wind_speed"],
        body["precipitation_probability"],
        body["precipitation_amount"],
        body["weather_code"],
        body["condition"],
        body["severe_alert"],
    ) == values[:9]
    assert body["source"] == "MOCK"
    assert body["context_status"] == "MOCK"

    forecast = client.get(
        f"/api/v1/context/weather/forecast?lat=18.93&lng=72.83&scenario={scenario}", headers=headers
    )
    assert forecast.status_code == 200, forecast.text
    forecast_body = forecast.json()[0]
    assert (
        forecast_body["temperature_c"],
        forecast_body["feels_like_c"],
        forecast_body["humidity"],
        forecast_body["wind_speed"],
        forecast_body["precipitation_probability"],
        forecast_body["precipitation_amount"],
        forecast_body["weather_code"],
        forecast_body["condition"],
        forecast_body["severe_alert"],
    ) == values[:9]
    assert forecast_body["source"] == "MOCK"
    assert forecast_body["context_status"] == "MOCK"


def test_weather_scenario_is_rejected_outside_development(client: TestClient) -> None:
    traveler = register_traveler(client, "weather-scenario-production@example.com")
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="production")
    response = client.get(
        "/api/v1/context/weather?lat=18.93&lng=72.83&scenario=SCENARIO_STORM",
        headers=auth_header(traveler),
    )
    assert response.status_code == 404


def _outdoor_experience() -> Experience:
    experience = Experience(
        provider=Provider(business_name="Scenario Test Provider", source_type="synthetic"),
        category=ExperienceCategory(slug="outdoor", name="Outdoor", sort_order=1),
        location=Location(latitude=18.93, longitude=72.83, source_type="synthetic"),
        title="Outdoor Fort Walk",
        short_description="Outdoor test experience",
        full_description="Outdoor test experience",
        price=100,
        price_type="fixed",
        price_source="estimated",
        duration_minutes=90,
        status="active",
        verification_status="verified",
        source_type="synthetic",
        environmental_type="OUTDOOR",
        weather_sensitivity="HIGH",
        weather_policy="SEVERE_WEATHER_EXCLUDE",
    )
    experience.id = "outdoor-experience"
    return experience


def test_scenarios_change_deterministic_weather_impact_without_replanning() -> None:
    now = datetime.now(UTC)
    clear = build_weather_scenario("SCENARIO_CLEAR", 18.93, 72.83)
    experience = _outdoor_experience()
    item = ItineraryItem(
        itinerary_id="test-itinerary",
        experience_id=experience.id,
        sequence_order=1,
        planned_start=now + timedelta(days=1),
        planned_end=now + timedelta(days=1, minutes=90),
        duration_minutes=90,
    )
    item.id = "test-itinerary-item"
    weather_impact = WeatherImpactService(Settings())
    context_impact = ContextImpactService(Settings())

    assert weather_impact.evaluate(experience, clear).status == WeatherImpactStatus.WEATHER_GOOD
    clear_result = context_impact.assess_weather(
        items=[item], experiences_by_id={experience.id: experience}, previous_weather=clear, new_weather=clear
    )
    assert clear_result.affected is False

    for scenario in ("SCENARIO_RAIN", "SCENARIO_STORM", "SCENARIO_HEAT"):
        weather = build_weather_scenario(scenario, 18.93, 72.83)
        assert weather.source == WeatherSource.MOCK
        assert weather_impact.evaluate(experience, weather).status == EXPECTED[scenario][-1]
        impact = context_impact.assess_weather(
            items=[item], experiences_by_id={experience.id: experience}, previous_weather=clear, new_weather=weather
        )
        assert impact.affected is True
        assert impact.affected_itinerary_item_ids == [item.id]
        assert impact.reason_codes == ["WEATHER_UNSUITABLE"]
