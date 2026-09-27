"""Canonical text construction for embeddings (Phase 6).

Two distinct builders, matching the asymmetric retrieval design:
  - `build_experience_document_text` — the DOCUMENT side, built only from
    real stored Experience fields. Never fabricates ratings, hours,
    availability, or accessibility; a missing field is simply omitted.
    `is_synthetic` provenance is preserved in the returned metadata dict
    so downstream code never loses that distinction, even though the text
    itself is prompt content, not a place to encode a boolean flag.
  - `build_query_text` — the QUERY side, built only from semantic-intent
    fields (interests, category, vibe/location text). Hard numeric
    constraints (budget, duration, travel time, capacity, hours,
    availability) never enter this text — those are exclusively
    FeasibilityService's job (docs/DECISIONS.md ADR-042/ADR-043).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from src.models.experience import Experience


@dataclass(frozen=True)
class ExperienceDocument:
    title: str
    text: str
    content_hash: str
    is_synthetic: bool


def build_experience_document_text(experience: Experience) -> ExperienceDocument:
    parts: list[str] = []

    parts.append(experience.title)
    if experience.category is not None:
        parts.append(f"Category: {experience.category.name}")
    if experience.short_description:
        parts.append(experience.short_description)
    if experience.full_description:
        parts.append(experience.full_description)
    if experience.tags:
        parts.append("Tags: " + ", ".join(experience.tags))
    if experience.suitability:
        parts.append("Suitable for: " + ", ".join(experience.suitability))
    if experience.location is not None:
        location_bits = [
            b
            for b in (experience.location.locality, experience.location.city)
            if b
        ]
        if location_bits:
            parts.append("Location: " + ", ".join(location_bits))

    text = "\n".join(parts)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return ExperienceDocument(
        title=experience.title,
        text=text,
        content_hash=content_hash,
        is_synthetic=experience.is_synthetic,
    )


def build_query_text(
    *,
    raw_query: str | None = None,
    interests: list[str] | None = None,
    category: str | None = None,
    location_text: str | None = None,
) -> str:
    """Semantic-intent-only query text. Deliberately excludes budget,
    duration, party size, time context, and accessibility — those are
    hard constraints handled by FeasibilityService, never stuffed into
    the semantic query embedding."""
    parts: list[str] = []
    if raw_query:
        parts.append(raw_query)
    if interests:
        parts.append("Interests: " + ", ".join(interests))
    if category:
        parts.append(f"Category: {category}")
    if location_text:
        parts.append(f"Near: {location_text}")
    return "\n".join(parts) if parts else (raw_query or "")


__all__ = ["ExperienceDocument", "build_experience_document_text", "build_query_text"]
