from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any


SOFT_LIST_FIELDS = ("interests", "food_preferences", "activities", "category_slugs")
SOFT_SCALAR_FIELDS = (
    "pace", "crowd_preference", "walking_tolerance_km", "budget_sensitivity", "preferred_duration_minutes"
)


def analyze_group_preferences(members: Iterable[dict[str, Any]]) -> dict[str, Any]:
    profiles = list(members)
    common: dict[str, list[str]] = {}
    flexible: dict[str, list[str]] = {}
    conflicts: dict[str, dict[str, int]] = {}
    group_direction: dict[str, str] = {}

    for field in SOFT_LIST_FIELDS:
        choices = [
            {str(value).strip().casefold() for value in profile.get("soft_preferences", {}).get(field, []) if str(value).strip()}
            for profile in profiles
        ]
        union = set().union(*choices) if choices else set()
        shared = set.intersection(*choices) if choices and all(choices) else set()
        common[field] = sorted(shared)
        flexible[field] = sorted(union - shared)

    for field in SOFT_SCALAR_FIELDS:
        ballots = [
            str(value).strip().casefold()
            for profile in profiles
            if (value := profile.get("soft_preferences", {}).get(field)) is not None
            and str(value).strip()
        ]
        counts = Counter(ballots)
        neutral_count = max(0, len(profiles) - len(ballots))
        if len(counts) > 1:
            conflicts[field] = dict(sorted(counts.items()))
            flexible[field] = [f"{neutral_count} neutral member(s)"] if neutral_count else []
        elif counts and neutral_count:
            group_direction[field] = next(iter(counts))
            flexible[field] = [f"{neutral_count} neutral member(s)"]
            common[field] = []
        else:
            common[field] = list(counts)
            flexible[field] = []

    warnings: list[str] = []
    if any(profile.get("hard_constraints", {}).get("age") is not None for profile in profiles):
        warnings.append(
            "Age was saved as a trip-specific member preference, but the current experience catalog has no verified age-limit fields; age restrictions cannot be checked."
        )
    unsupported_soft_fields = ("pace", "crowd_preference", "walking_tolerance_km", "budget_sensitivity")
    if any(
        profile.get("soft_preferences", {}).get(field) is not None
        for profile in profiles
        for field in unsupported_soft_fields
    ):
        warnings.append(
            "Pace, crowd, walking tolerance, and budget sensitivity are included in the group profile, but the catalog does not provide verified candidate-level fields for matching them."
        )
    return {
        "common": common,
        "flexible": flexible,
        "conflicts": conflicts,
        "group_direction": group_direction,
        "warnings": warnings,
    }


def _matching_text(experience: Any) -> str:
    category = getattr(getattr(experience, "category", None), "name", "")
    values = [
        getattr(experience, "title", ""),
        getattr(experience, "short_description", ""),
        getattr(experience, "full_description", ""),
        category,
    ]
    values.extend(getattr(experience, "tags", None) or [])
    values.extend(getattr(experience, "suitability", None) or [])
    return " ".join(str(value) for value in values if value).casefold()


def score_group_experience(
    experience: Any,
    members: list[dict[str, Any]],
    objectives: dict[str, Any],
) -> dict[str, Any]:
    text = _matching_text(experience)
    satisfaction: dict[str, float] = {}
    matched: list[str] = []

    for member in members:
        preferences = member.get("soft_preferences", {})
        positive_terms: list[tuple[str, str]] = []
        for field in SOFT_LIST_FIELDS:
            positive_terms.extend(
                (field, str(value).strip())
                for value in preferences.get(field, [])
                if str(value).strip()
            )
        preferred_duration = preferences.get("preferred_duration_minutes")
        if preferred_duration is not None:
            positive_terms.append(("preferred_duration_minutes", _duration_band(int(preferred_duration))))

        matched_terms: list[str] = []
        for field, term in positive_terms:
            if field == "category_slugs":
                matches = term.casefold() == str(getattr(getattr(experience, "category", None), "slug", "")).casefold()
            elif field == "preferred_duration_minutes":
                duration = getattr(experience, "duration_minutes", None)
                matches = duration is not None and _duration_band(duration) == term
            else:
                matches = term.casefold() in text
            if matches:
                matched_terms.append(term)
                matched.append(f"{field.replace('_', ' ').title()}: {term}")
        explicit = bool(positive_terms or preferences.get("dislikes"))
        member_score = len(matched_terms) / len(positive_terms) if positive_terms else 0.75
        disliked = [
            str(value).strip()
            for value in preferences.get("dislikes", [])
            if str(value).strip() and str(value).casefold() in text
        ]
        if disliked:
            member_score = max(0.0, member_score - min(0.75, 0.35 * len(disliked)))
            matched.extend(f"Avoided: {term}" for term in disliked)
        if explicit:
            satisfaction[str(member["id"])] = round(member_score, 3)

    objective_terms = [
        str(term).strip()
        for key in ("interests", "must_include", "activities")
        for term in objectives.get(key, [])
        if str(term).strip()
    ]
    objective_matches = [term for term in objective_terms if term.casefold() in text]
    objective_score = len(objective_matches) / len(objective_terms) if objective_terms else 0.0
    matched.extend(f"Group objective: {term}" for term in objective_matches)

    if satisfaction:
        scores = list(satisfaction.values())
        mean_score = sum(scores) / len(scores)
        fair_score = 0.6 * mean_score + 0.4 * min(scores)
        compatibility = 0.8 * fair_score + 0.2 * objective_score if objective_terms else fair_score
    else:
        compatibility = objective_score

    return {
        "compatibility_score": round(compatibility * 100, 1),
        "group_objective_score": round(objective_score * 100, 1),
        "member_satisfaction": satisfaction,
        "matched_preferences": sorted(set(matched)),
    }


def _duration_band(minutes: int) -> str:
    if minutes < 60:
        return "< 60 min"
    if minutes <= 180:
        return "1-3 hrs"
    return "3+ hrs"


__all__ = ["analyze_group_preferences", "score_group_experience"]
