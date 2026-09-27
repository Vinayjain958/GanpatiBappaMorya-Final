"""WeatherImpactService — deterministic weather-suitability evaluation (Phase 9).

Evaluates an experience's environmental profile (environmental_type,
weather_sensitivity, weather_policy — src/models/experience.py) against a
forecast WeatherContext for its planned window. 100% deterministic, no
LLM involvement — Gemini never decides weather suitability
(docs/AI_CONTEXT.md hard invariant).

Statuses: WEATHER_GOOD / WEATHER_CAUTION / WEATHER_UNSUITABLE /
WEATHER_UNKNOWN. UNKNOWN whenever the experience's environmental
metadata OR the weather context itself is unavailable/unknown — never
upgraded to GOOD by assumption (mirrors FeasibilityService's UNKNOWN
contract from Phase 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from src.adapters.weather import WeatherContext, WeatherSource
from src.core.config import Settings
from src.models.experience import Experience


class WeatherImpactStatus(StrEnum):
    WEATHER_GOOD = "WEATHER_GOOD"
    WEATHER_CAUTION = "WEATHER_CAUTION"
    WEATHER_UNSUITABLE = "WEATHER_UNSUITABLE"
    WEATHER_UNKNOWN = "WEATHER_UNKNOWN"


@dataclass
class WeatherImpactVerdict:
    status: WeatherImpactStatus
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)


class WeatherImpactService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def evaluate(self, experience: Experience, weather: WeatherContext) -> WeatherImpactVerdict:
        if weather.source == WeatherSource.UNAVAILABLE:
            return WeatherImpactVerdict(
                status=WeatherImpactStatus.WEATHER_UNKNOWN,
                reasons=["Weather context is unavailable."],
            )

        # None can occur on an unpersisted in-memory Experience (SQLAlchemy
        # column defaults apply at INSERT, not object construction) —
        # treated identically to the persisted "UNKNOWN" default rather
        # than ever assumed to mean something more permissive.
        env_type = experience.environmental_type or "UNKNOWN"
        policy = experience.weather_policy or "NONE"
        sensitivity = experience.weather_sensitivity or "UNKNOWN"

        if env_type == "UNKNOWN" or sensitivity == "UNKNOWN":
            return WeatherImpactVerdict(
                status=WeatherImpactStatus.WEATHER_UNKNOWN,
                reasons=["Experience has no known environmental/weather metadata."],
            )

        # Indoor experiences with no explicit severe-weather exclusion
        # policy are unaffected by outdoor conditions.
        if env_type == "INDOOR" and policy != "SEVERE_WEATHER_EXCLUDE":
            return WeatherImpactVerdict(status=WeatherImpactStatus.WEATHER_GOOD, reasons=["Indoor experience."])

        reasons: list[str] = []
        evidence: dict[str, object] = {
            "environmental_type": env_type,
            "weather_sensitivity": sensitivity,
            "weather_policy": policy,
        }

        if weather.severe_alert:
            reasons.append("Severe weather alert active for the planned window.")
            return WeatherImpactVerdict(status=WeatherImpactStatus.WEATHER_UNSUITABLE, reasons=reasons, evidence=evidence)

        settings = self._settings
        precip_prob = weather.precipitation_probability
        precip_amount = weather.precipitation_amount
        wind = weather.wind_speed
        temp = weather.temperature_c

        unsuitable = False
        caution = False

        if precip_prob is not None:
            evidence["precipitation_probability"] = precip_prob
            if precip_prob >= settings.weather_precipitation_probability_threshold:
                if policy == "SEVERE_WEATHER_EXCLUDE" or sensitivity == "HIGH":
                    unsuitable = True
                    reasons.append(f"High precipitation probability ({precip_prob}%).")
                elif policy != "LIGHT_RAIN_OK":
                    caution = True
                    reasons.append(f"Elevated precipitation probability ({precip_prob}%).")
            elif precip_prob >= (
                settings.weather_precipitation_probability_threshold - settings.weather_impact_hysteresis_pct
            ) and policy not in ("LIGHT_RAIN_OK", "NONE"):
                caution = True
                reasons.append(f"Borderline precipitation probability ({precip_prob}%).")

        if precip_amount is not None:
            evidence["precipitation_amount"] = precip_amount
            if precip_amount >= settings.weather_precipitation_amount_mm_threshold:
                if policy == "LIGHT_RAIN_OK":
                    caution = True
                else:
                    unsuitable = True
                reasons.append(f"Precipitation amount {precip_amount}mm.")

        if wind is not None:
            evidence["wind_speed"] = wind
            if wind >= settings.weather_wind_speed_threshold_ms:
                if sensitivity == "HIGH":
                    unsuitable = True
                else:
                    caution = True
                reasons.append(f"High wind speed ({wind} m/s).")

        if temp is not None:
            evidence["temperature_c"] = temp
            if temp <= settings.weather_temperature_extreme_low_c or temp >= settings.weather_temperature_extreme_high_c:
                if sensitivity == "HIGH":
                    unsuitable = True
                else:
                    caution = True
                reasons.append(f"Extreme temperature ({temp}°C).")

        if policy == "SEVERE_WEATHER_EXCLUDE" and unsuitable:
            status = WeatherImpactStatus.WEATHER_UNSUITABLE
        elif unsuitable:
            status = WeatherImpactStatus.WEATHER_UNSUITABLE
        elif caution:
            status = WeatherImpactStatus.WEATHER_CAUTION
        else:
            status = WeatherImpactStatus.WEATHER_GOOD
            reasons = reasons or ["Conditions within configured thresholds."]

        return WeatherImpactVerdict(status=status, reasons=reasons, evidence=evidence)


__all__ = ["WeatherImpactService", "WeatherImpactStatus", "WeatherImpactVerdict"]
