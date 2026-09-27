"""Deterministic duplicate detection for traveler experience contributions.

No AI/Gemini in the match decision — matching is entirely
rule-based on normalized name similarity, geographic proximity
(`core/geo.py::haversine_km`, the same primitive used everywhere else in
this codebase for distance), phone number equality, and website domain
equality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlparse

from src.core.geo import haversine_km
from src.models.experience import Experience

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_DIGITS_RE = re.compile(r"\D+")


def normalize_name(name: str) -> str:
    lowered = name.strip().lower()
    stripped = _PUNCTUATION_RE.sub("", lowered)
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def normalize_phone(phone: str) -> str:
    return _DIGITS_RE.sub("", phone)


def phones_match(a: str, b: str) -> bool:
    """Compares two already-digits-only phone numbers for equality,
    tolerant of one having a country code the other lacks (a country
    code is never assumed or invented, but duplicate detection still
    needs "+91 98765 43210" to match a bare "9876543210" from an older
    catalog record) — compares by the shorter number being a suffix of
    the longer one, requiring at least 7 digits so this never false-
    -positives on short/garbage input."""
    if not a or not b:
        return False
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < 7:
        return a == b
    return longer.endswith(shorter)


def normalize_website_domain(url: str) -> str:
    parsed = urlparse(url if "//" in url else f"//{url}")
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _name_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


@dataclass(frozen=True)
class DuplicateMatch:
    experience: Experience
    tier: str  # "strong" | "uncertain"
    reason: str


def find_duplicate_match(
    candidates: list[Experience],
    *,
    name: str,
    latitude: float,
    longitude: float,
    phone: str,
    website: str | None,
    radius_m: float,
    contributed_contacts: dict[str, tuple[str | None, str | None]] | None = None,
) -> DuplicateMatch | None:
    """Returns the single best match (strong beats uncertain, closest
    beats farther), or None if nothing meets even the uncertain bar.

    `contributed_contacts` maps an experience id to the (phone, website) its
    traveler contributor submitted. Community-added places share one
    placeholder provider with no contact details of its own, so without
    this their phone/website could never match."""
    contributed_contacts = contributed_contacts or {}
    normalized_name = normalize_name(name)
    normalized_phone = normalize_phone(phone)
    normalized_domain = normalize_website_domain(website) if website else None
    radius_km = radius_m / 1000.0

    best: DuplicateMatch | None = None
    best_distance_km = float("inf")

    for candidate in candidates:
        if candidate.location is None:
            continue
        distance_km = haversine_km(
            latitude, longitude, candidate.location.latitude, candidate.location.longitude
        )
        candidate_name = normalize_name(candidate.title)
        contributed_phone, contributed_website = contributed_contacts.get(candidate.id, (None, None))
        raw_phone = contributed_phone or (candidate.provider.contact_phone if candidate.provider else None)
        raw_website = contributed_website or (candidate.provider.website if candidate.provider else None)
        candidate_phone = normalize_phone(raw_phone or "")
        candidate_domain = normalize_website_domain(raw_website) if raw_website else None
        ratio = _name_ratio(normalized_name, candidate_name) if candidate_name else 0.0

        tier: str | None = None
        reason = ""

        if normalized_phone and candidate_phone and phones_match(normalized_phone, candidate_phone):
            if distance_km <= radius_km:
                tier, reason = "strong", "same phone number and nearby location"
            else:
                tier, reason = "uncertain", "same phone number, but far apart"
        elif ratio >= 0.92 and distance_km <= radius_km:
            tier, reason = "strong", "matching name and nearby location"
        elif (
            normalized_domain
            and candidate_domain
            and normalized_domain == candidate_domain
            and ratio >= 0.6
        ):
            tier, reason = "strong", "matching website and similar name"
        elif ratio >= 0.75 and distance_km <= radius_km * 2:
            tier, reason = "uncertain", "similar name nearby"

        if tier is None:
            continue

        # Strong always wins over uncertain; among same-tier matches,
        # prefer the closest one.
        if best is None or (tier == "strong" and best.tier == "uncertain") or (
            tier == best.tier and distance_km < best_distance_km
        ):
            best = DuplicateMatch(experience=candidate, tier=tier, reason=reason)
            best_distance_km = distance_km

    return best
