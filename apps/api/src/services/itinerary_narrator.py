"""ItineraryNarratorService — Gemini narrative generation (Phase 8).

Uses the existing AIAdapter (src/adapters/ai.py) — no second AI client.
Input is restricted to backend-validated facts only: the already-VALID
itinerary's items, canonical Experience facts, validated times/gaps/
costs, and current booking status. Gemini never receives raw traveler
free text here and is never asked for (or trusted with) feasibility,
timing, or booking-confirmation decisions — those are already decided
before this service is ever called (see src/services/itinerary_composer
flow in src/api/v1/itineraries.py: RETRIEVAL -> FEASIBILITY -> RANKING ->
COMPOSITION -> POST-COMPOSITION VALIDATION -> NARRATIVE, in that order).

On any Gemini failure (adapter error, timeout, invalid structured output)
this service falls back to a deterministic backend template — the
itinerary's validity never depends on narrative success.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from src.adapters.ai import AIAdapter
from src.adapters.errors import AdapterError
from src.core.config import Settings
from src.services.experience_composer import ComposedItem

NARRATOR_SYSTEM_INSTRUCTION = (
    "You are LocaLens's itinerary narrator. You will be given an already "
    "backend-validated itinerary: a fixed, chronological list of "
    "experiences with their real title, price, duration, and location, "
    "plus travel gaps between them and the current booking-request status "
    "of each item. Write warm, concise narrative text ONLY from these "
    "supplied facts. You may NEVER invent or alter a price, duration, "
    "opening hours, review, rating, availability, transport time, "
    "location, or experience id — use only the values given to you. You "
    "may NEVER claim a booking is confirmed; a REQUESTED booking status "
    "must be described as requested/pending, never as confirmed or "
    "guaranteed. If a travel gap is marked unknown, say the travel time "
    "is not available rather than guessing a number. Do not add "
    "experiences, stops, or time slots that were not given to you. Only "
    "mention booking status for an item when a booking_status fact is "
    "actually present for it — most items will have none, meaning no "
    "booking has been requested, and in that case you must not mention "
    "booking at all for that item (never write a filler line like "
    "\"booking is not requested\")."
)


class ItemNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    text: str = Field(max_length=400)


class NarrativeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=120)
    summary: str = Field(max_length=600)
    itinerary_intro: str = Field(max_length=400)
    item_narratives: list[ItemNarrative] = Field(default_factory=list)
    travel_notes: str = Field(default="", max_length=400)
    booking_notes: str = Field(default="", max_length=400)
    closing_message: str = Field(max_length=300)


@dataclass
class NarrationOutcome:
    narrative: NarrativeResponse
    model_version: str
    used_fallback: bool


def _facts_prompt(
    *,
    items: list[ComposedItem],
    itinerary_date_str: str,
    currency: str,
    total_cost: float,
    booking_statuses: dict[str, str],
) -> str:
    lines = [
        "Backend-validated itinerary facts (use ONLY these — never invent "
        "or change any value):",
        f"Date: {itinerary_date_str}",
        f"Total estimated cost: {total_cost} {currency}",
        "Items in fixed chronological order:",
    ]
    for item in items:
        # Only surface a booking_status fact when something has actually
        # happened (REQUESTED/ACCEPTED/DECLINED/...) — omitting it for the
        # (overwhelmingly common) "nothing requested yet" case means
        # there's no fact for Gemini to narrate into a repetitive filler
        # line on every single item.
        booking_status = booking_statuses.get(item.experience.id)
        booking_fact = f" booking_status={booking_status}" if booking_status else ""
        lines.append(
            f"- id={item.experience.id} title=\"{item.experience.title}\" "
            f"category={item.experience.category.name} "
            f"start={item.planned_start.isoformat()} end={item.planned_end.isoformat()} "
            f"duration_minutes={item.duration_minutes} "
            f"price={item.estimated_cost if item.estimated_cost is not None else 'unknown'} {currency} "
            f"travel_from_previous_minutes="
            f"{item.travel_from_previous_minutes if item.travel_from_previous_minutes is not None else 'unknown'}"
            f"{booking_fact}"
        )
    lines.append(
        "Respond with the requested structured fields only, referencing "
        "experiences strictly by the ids given above."
    )
    return "\n".join(lines)


def _template_fallback(
    *,
    items: list[ComposedItem],
    total_cost: float,
    currency: str,
    booking_statuses: dict[str, str],
) -> NarrativeResponse:
    """Deterministic, no-LLM narrative — used whenever Gemini is
    unavailable, times out, or returns an invalid structured result. The
    itinerary itself is already valid at this point; only the narrative
    text is templated."""
    count = len(items)
    title = f"Your {count}-stop itinerary" if count != 1 else "Your itinerary"
    summary = (
        f"{count} experience{'s' if count != 1 else ''} planned, "
        f"totalling an estimated {total_cost} {currency}."
    )
    intro = "Here is your planned schedule, in order:"
    item_narratives = [
        ItemNarrative(
            experience_id=item.experience.id,
            text=(
                f"{item.experience.title} — {item.planned_start.strftime('%H:%M')} to "
                f"{item.planned_end.strftime('%H:%M')}."
            ),
        )
        for item in items
    ]
    travel_notes = "Travel times between stops are shown where known." if any(
        i.travel_from_previous_minutes is not None for i in items
    ) else ""
    any_requested = any(v == "REQUESTED" for v in booking_statuses.values())
    booking_notes = (
        "Booking requests shown as REQUESTED are pending provider confirmation — not yet confirmed."
        if any_requested
        else ""
    )
    closing = "Have a great trip!"
    return NarrativeResponse(
        title=title,
        summary=summary,
        itinerary_intro=intro,
        item_narratives=item_narratives,
        travel_notes=travel_notes,
        booking_notes=booking_notes,
        closing_message=closing,
    )


class ItineraryNarratorService:
    def __init__(self, ai_adapter: AIAdapter, settings: Settings) -> None:
        self._ai = ai_adapter
        self._settings = settings

    async def narrate(
        self,
        *,
        items: list[ComposedItem],
        itinerary_date_str: str,
        currency: str,
        total_cost: float,
        booking_statuses: dict[str, str] | None = None,
    ) -> NarrationOutcome:
        booking_statuses = booking_statuses or {}
        fallback = _template_fallback(
            items=items, total_cost=total_cost, currency=currency, booking_statuses=booking_statuses
        )
        if not items:
            return NarrationOutcome(
                narrative=fallback,
                model_version=self._settings.composer_template_narrative_version,
                used_fallback=True,
            )

        prompt = (
            f"{NARRATOR_SYSTEM_INSTRUCTION}\n\n"
            + _facts_prompt(
                items=items,
                itinerary_date_str=itinerary_date_str,
                currency=currency,
                total_cost=total_cost,
                booking_statuses=booking_statuses,
            )
        )

        try:
            narrative = await self._ai.generate_text(prompt, response_schema=NarrativeResponse)
        except (AdapterError, ValueError, Exception):  # noqa: BLE001 — any Gemini failure -> deterministic fallback
            return NarrationOutcome(
                narrative=fallback,
                model_version=self._settings.composer_template_narrative_version,
                used_fallback=True,
            )

        # Never let a hallucinated experience_id reach the response — drop
        # any item_narrative whose id wasn't in the supplied fact set.
        valid_ids = {item.experience.id for item in items}
        narrative.item_narratives = [
            n for n in narrative.item_narratives if n.experience_id in valid_ids
        ]

        return NarrationOutcome(
            narrative=narrative,
            model_version=self._settings.composer_narrative_model_version,
            used_fallback=False,
        )


__all__ = [
    "ItemNarrative",
    "ItineraryNarratorService",
    "NARRATOR_SYSTEM_INSTRUCTION",
    "NarrationOutcome",
    "NarrativeResponse",
]
