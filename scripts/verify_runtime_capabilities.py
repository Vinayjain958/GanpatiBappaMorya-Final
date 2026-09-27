#!/usr/bin/env python3
"""Read-only LocaLens runtime checks for weather, map, social, and what-if.

Uses only the Python standard library. It never prints TOKEN, calls an apply
endpoint, edits data, or fabricates an itinerary. What-if simulation is opt-in
and requires an existing itinerary ID; the API creates only its normal
ephemeral preview session.

Usage:
    python3 scripts/verify_runtime_capabilities.py
    TOKEN=... python3 scripts/verify_runtime_capabilities.py
    TOKEN=... python3 scripts/verify_runtime_capabilities.py \
        --itinerary-id EXISTING_ID --run-what-if-preview

Override local server URLs with LOCALELENS_API_URL / LOCALELENS_WEB_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_LATITUDE = 19.0760
DEFAULT_LONGITUDE = 72.8777
ROUTE_TERMS = (
    "weather",
    "context",
    "map",
    "location",
    "route",
    "social",
    "signal",
    "trend",
    "simulation",
    "simulate",
    "twin",
    "what-if",
    "whatif",
    "replan",
    "overture",
    "source-data",
)


@dataclass
class Response:
    status: int
    payload: Any = None
    text: str = ""
    error: str | None = None


def request(
    url: str,
    *,
    token: str | None = None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 10,
) -> Response:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            text = response.read().decode("utf-8", "replace")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            return Response(response.status, payload, text)
    except HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        return Response(exc.code, payload, text)
    except (TimeoutError, URLError, OSError) as exc:
        return Response(0, error=type(exc).__name__)


def summarize(status: str, evidence: str) -> None:
    print(f"Status: {status} — {evidence}")


def is_auth_block(response: Response) -> bool:
    return response.status in (401, 403)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.getenv("LOCALELENS_API_URL", "http://localhost:8000"),
        help="API origin (default: LOCALELENS_API_URL or localhost:8000)",
    )
    parser.add_argument(
        "--web-url",
        default=os.getenv("LOCALELENS_WEB_URL", "http://localhost:3000"),
        help="Web origin (default: LOCALELENS_WEB_URL or localhost:3000)",
    )
    parser.add_argument(
        "--itinerary-id",
        help="Existing itinerary owned by TOKEN; required for an opt-in preview",
    )
    parser.add_argument(
        "--run-what-if-preview",
        action="store_true",
        help="Submit a hypothetical preview only; never applies it",
    )
    args = parser.parse_args()

    if args.run_what_if_preview and not args.itinerary_id:
        parser.error("--run-what-if-preview requires --itinerary-id for a real itinerary")
    if args.itinerary_id and not args.run_what_if_preview:
        parser.error("pass --run-what-if-preview to use --itinerary-id")

    api_url = args.api_url.rstrip("/")
    web_url = args.web_url.rstrip("/")
    token = os.getenv("TOKEN") or None

    print("LOCALELENS RUNTIME CAPABILITY CHECK")
    print(f"API: {api_url}")
    print(f"Web: {web_url}")
    print(f"TOKEN available: {'yes' if token else 'no'} (value is never displayed)")

    spec_response = request(f"{api_url}/openapi.json")
    if spec_response.status != 200 or not isinstance(spec_response.payload, dict):
        summarize("FAIL", f"OpenAPI unavailable (HTTP {spec_response.status or 'network error'})")
        return 2

    paths = spec_response.payload.get("paths", {})
    matching_routes = [
        (path, ",".join(method.upper() for method in methods))
        for path, methods in paths.items()
        if any(term in path.casefold() for term in ROUTE_TERMS)
    ]
    print("\nAPI routes discovered:")
    for path, methods in matching_routes:
        print(f"  {methods:10} {path}")

    print("\n1. LIVE WEATHER")
    weather_url = f"{api_url}/api/v1/context/weather?{urlencode({'lat': DEFAULT_LATITUDE, 'lng': DEFAULT_LONGITUDE})}"
    weather = request(weather_url, token=token)
    forecast_url = f"{api_url}/api/v1/context/weather/forecast?{urlencode({'lat': DEFAULT_LATITUDE, 'lng': DEFAULT_LONGITUDE})}"
    forecast = request(forecast_url, token=token)
    if is_auth_block(weather) or is_auth_block(forecast):
        summarize("PARTIAL", "weather/forecast requires a valid bearer token; adapter and live status cannot be inspected")
        print(f"  current HTTP {weather.status}; forecast HTTP {forecast.status}")
    elif weather.status == 200 and isinstance(weather.payload, dict):
        source = weather.payload.get("source")
        context_status = weather.payload.get("context_status")
        freshness = weather.payload.get("fetched_at") or weather.payload.get("last_updated_at")
        populated = any(
            weather.payload.get(field) is not None
            for field in ("temperature_c", "condition", "humidity", "wind_speed")
        )
        if source == "MOCK" or context_status == "MOCK":
            summarize("MOCK", "backend returned development/mock weather")
        elif source == "LIVE" and context_status == "LIVE" and freshness and populated:
            summarize("PASS", f"current weather is LIVE with normalized fields and freshness timestamp {freshness}")
        else:
            summarize("PARTIAL", f"current weather source={source}, context_status={context_status}, populated={populated}")
        if forecast.status == 200 and isinstance(forecast.payload, list):
            print(f"  forecast HTTP 200; entries={len(forecast.payload)}")
        else:
            print(f"  forecast HTTP {forecast.status}")
    else:
        summarize("FAIL", f"weather endpoint returned HTTP {weather.status or 'network error'}")

    print("\n2. MAP VISUALIZATION")
    discover = request(f"{web_url}/discover")
    if discover.status == 200:
        params = urlencode({"limit": 24, "offset": 0, "is_synthetic": "false"})
        experiences = request(f"{api_url}/api/v1/experiences?{params}", token=token)
        if experiences.status == 200 and isinstance(experiences.payload, dict):
            entries = experiences.payload.get("items", [])
            synthetic_count = sum(
                1 for item in entries if isinstance(item, dict) and item.get("is_synthetic") is True
            ) if isinstance(entries, list) else 0
            print(f"  non-demo experience API HTTP 200; returned={len(entries) if isinstance(entries, list) else 'unknown'}; synthetic={synthetic_count}")
        else:
            print(f"  non-demo experience API HTTP {experiences.status or 'network error'}")
        source_data = request(f"{api_url}/api/v1/experiences/source-data/overture")
        if source_data.status == 200 and isinstance(source_data.payload, dict):
            print(
                "  raw source snapshot HTTP 200; "
                f"records={source_data.payload.get('record_count')}; "
                f"synthetic={source_data.payload.get('synthetic_records_included')}; "
                f"live={source_data.payload.get('is_live')}"
            )
        else:
            print(f"  raw source snapshot HTTP {source_data.status or 'network error'}")
        summarize("PARTIAL", "Discover route and non-demo map data checked; HTTP cannot prove client-side MapLibre canvas or tile rendering")
        print("  Open /discover in a browser to confirm the basemap, experience markers, and any route overlay.")
    else:
        summarize("FAIL", f"Discover route returned HTTP {discover.status or 'network error'}")

    print("\n3. SOCIAL SIGNALS")
    social_query = urlencode({"lat": DEFAULT_LATITUDE, "lng": DEFAULT_LONGITUDE})
    social = request(f"{api_url}/api/v1/twin/social-signals?{social_query}", token=token)
    if is_auth_block(social):
        summarize("PARTIAL", "social endpoint requires a valid bearer token; provider result is unverified")
        print(f"  HTTP {social.status}")
    elif social.status == 200 and isinstance(social.payload, dict):
        social_status = social.payload.get("status")
        generated_at = social.payload.get("generated_at")
        if social_status in ("AVAILABLE", "NO_SIGNALS") and generated_at:
            summarize("PASS", f"backend returned normalized social status={social_status} at {generated_at}")
        else:
            summarize("PARTIAL", f"backend returned status={social_status}; provider data is incomplete or stale")
    else:
        summarize("FAIL", f"social endpoint returned HTTP {social.status or 'network error'}")

    print("\n4. DIGITAL TWIN / WHAT-IF")
    if not args.run_what_if_preview:
        summarize("PARTIAL", "preview not run; provide TOKEN, an existing owned --itinerary-id, and --run-what-if-preview")
        print("  The checker never calls the separate /simulations/{id}/apply endpoint.")
    elif not token:
        summarize("PARTIAL", "TOKEN is required; no simulation request was sent")
    else:
        itinerary_url = f"{api_url}/api/v1/itineraries/{args.itinerary_id}"
        before = request(itinerary_url, token=token)
        before_version = before.payload.get("version") if isinstance(before.payload, dict) else None
        if before.status != 200 or not isinstance(before_version, int):
            summarize("PARTIAL", f"could not verify ownership/read itinerary version before preview (HTTP {before.status})")
            print("  No simulation request was sent.")
            print("\nLimits: server secrets are never inspected or printed; unavailable auth/config/data stays unverified.")
            return 0

        simulation_url = f"{api_url}/api/v1/digital-twin/itineraries/{args.itinerary_id}/simulate"
        preview = request(
            simulation_url,
            token=token,
            method="POST",
            body={
                "name": "Runtime verification preview",
                "horizon_hours": 24,
                "weather": {"intensity": "light_rain", "starts_at": "17:00:00"},
            },
        )
        if preview.status == 200 and isinstance(preview.payload, dict):
            simulation_status = preview.payload.get("status")
            has_scenario = isinstance(preview.payload.get("scenario"), dict)
            has_baseline = isinstance(preview.payload.get("baseline"), dict)
            after = request(itinerary_url, token=token)
            after_version = after.payload.get("version") if isinstance(after.payload, dict) else None
            unchanged = after.status == 200 and after_version == before_version
            result_status = "PASS" if simulation_status == "READY" and has_scenario and has_baseline and unchanged else "PARTIAL"
            summarize(result_status, f"preview HTTP 200; status={simulation_status}; scenario/baseline present={has_scenario}/{has_baseline}; itinerary version unchanged={unchanged}")
            print("  Preview only; no apply request is made. It creates the API's normal short-lived preview session.")
        elif is_auth_block(preview):
            summarize("PARTIAL", f"simulation requires a valid traveler token (HTTP {preview.status})")
        else:
            summarize("FAIL", f"simulation returned HTTP {preview.status or 'network error'}")

    print("\nLimits: server secrets are never inspected or printed; unavailable auth/config/data stays unverified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
