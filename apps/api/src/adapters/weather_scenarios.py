"""Ephemeral weather test inputs for local development only.

These values are never fetched from or written to OpenWeather and are
returned with source MOCK. Production routes reject scenario requests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from src.adapters.weather import WeatherContext, WeatherSource

WeatherScenario = Literal["SCENARIO_CLEAR", "SCENARIO_RAIN", "SCENARIO_STORM", "SCENARIO_HEAT"]

_SCENARIOS: dict[WeatherScenario, tuple[float, float, float, float, float, float, int, str, bool]] = {
    "SCENARIO_CLEAR": (28, 30, 60, 2, 0, 0, 800, "Clear", False),
    "SCENARIO_RAIN": (26, 27, 90, 4, 90, 8, 500, "Rain", False),
    "SCENARIO_STORM": (24, 25, 95, 15, 100, 20, 200, "Thunderstorm", True),
    "SCENARIO_HEAT": (40, 45, 70, 2, 0, 0, 800, "Clear", False),
}


def build_weather_scenario(scenario: WeatherScenario, latitude: float, longitude: float) -> WeatherContext:
    """Build one non-persistent MOCK context for API/UI verification."""
    now = datetime.now(UTC)
    temperature, feels_like, humidity, wind, rain_chance, precipitation, code, condition, severe = _SCENARIOS[
        scenario
    ]
    return WeatherContext(
        latitude=latitude,
        longitude=longitude,
        observed_at=now,
        timezone=None,
        temperature_c=temperature,
        feels_like_c=feels_like,
        humidity=humidity,
        wind_speed=wind,
        precipitation_probability=rain_chance,
        precipitation_amount=precipitation,
        weather_code=code,
        condition=condition,
        visibility_km=10.0,
        severe_alert=severe,
        source=WeatherSource.MOCK,
        source_timestamp=now,
        fetched_at=now,
        expires_at=now + timedelta(minutes=5),
    )


__all__ = ["WeatherScenario", "build_weather_scenario"]
