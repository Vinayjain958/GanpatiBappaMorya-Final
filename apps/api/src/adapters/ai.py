"""AIAdapter — Gemini text generation and ephemeral Live token issuance.

Real implementation uses the official `google-genai` SDK (not raw httpx —
the SDK owns its own transport/auth). `MockAIAdapter` is used whenever
Gemini is disabled or unconfigured (see src/core/ai.py); text mode stays
usable via a deterministic, cheap keyword extraction, but voice is never
faked — issuing a live token without real Gemini always fails loudly
rather than pretending a connection exists (docs/DECISIONS.md ADR-034).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from src.adapters.errors import AdapterNoResultError, AdapterRateLimitedError, AdapterUnavailableError
from src.core.config import Settings
from src.core.rate_limit import IntervalRateLimiter
from src.schemas.conversation import TravelerContext

T = TypeVar("T", bound=BaseModel)


def _gemini_safe_schema(model: type[BaseModel]) -> dict[str, object]:
    """Pydantic's `extra="forbid"` emits `additionalProperties: false` in
    the generated JSON Schema; Gemini's response_schema endpoint rejects
    `additionalProperties` outright ("Unknown name ... Cannot find
    field"). Strip it (recursively, including $defs) rather than relax
    the model's own request-validation strictness elsewhere."""

    def strip(node: object) -> object:
        if isinstance(node, dict):
            return {
                key: strip(value)
                for key, value in node.items()
                if key != "additionalProperties"
            }
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    return strip(model.model_json_schema())  # type: ignore[return-value]


@dataclass(frozen=True)
class LiveTokenIssueResult:
    token: str
    expire_time: datetime
    new_session_expire_time: datetime
    model: str


class AIAdapter(Protocol):
    async def generate_text(self, prompt: str, *, response_schema: type[T]) -> T: ...

    async def issue_live_token(self) -> LiveTokenIssueResult: ...


# Live voice system instruction (Phase 6, docs/DECISIONS.md ADR-044):
# locked into the ephemeral token via lock_additional_fields so the
# browser can never alter it. Explicitly scopes the model to backend-owned
# tools, including the read-only what-if preview, and forbids inventing facts
# or phrasing UNKNOWN as safe.
LIVE_SYSTEM_INSTRUCTION = (
    "You are LocaLens's voice discovery assistant. You may only call the "
    "search_experiences, check_feasibility, compose_experience, "
    "replan_experience, and simulate_what_if tools — never answer a question about a specific "
    "experience's price, "
    "hours, capacity, availability, or accessibility from your own "
    "knowledge or by guessing; always call check_feasibility first and "
    "report only what it returns. Never claim an experience is feasible, "
    "affordable, open, or accessible without tool evidence for that "
    "specific claim. If check_feasibility returns UNKNOWN for a "
    "constraint, tell the traveler that information is not available — "
    "never phrase UNKNOWN as 'probably fine', 'should be okay', or "
    "similarly reassuring. Never invent an experience, id, price, or fact "
    "that a tool did not return. When composing an itinerary, only call "
    "compose_experience with experience_ids that search_experiences just "
    "returned in this conversation — never invent an id. compose_experience "
    "decides ordering, timing, travel gaps, and feasibility deterministically "
    "— you never override or guess at any of that yourself, and you never "
    "claim a booking is confirmed; a booking request is only ever "
    "'requested' until a provider accepts it. When a traveler wants an "
    "existing itinerary changed (a different time, budget, party size, or "
    "a specific experience swapped), call replan_experience — it never "
    "directly edits the itinerary itself, only asks the backend's "
    "deterministic replanning pipeline to re-plan the affected part. You "
    "never decide weather suitability, event cancellation, schedule "
    "conflicts, or itinerary validity yourself — only narrate the "
    "structured result replan_experience returns, honestly reporting "
    "REPLAN_FAILED or REQUIRES_USER_ACTION outcomes rather than claiming "
    "success. When the traveler asks to explore a hypothetical, you may call "
    "simulate_what_if to create a read-only preview. Clearly label assumptions "
    "as hypothetical; the preview never applies or persists changes. Only the "
    "traveler's explicit UI action can apply a still-current preview through "
    "the backend replanning service."
)

_STOPWORDS = {
    "a", "an", "and", "the", "for", "with", "near", "in", "at", "to", "of", "i", "im", "i'm",
    "want", "looking", "have", "got", "we", "us", "our", "my", "me", "some", "something",
}


def _latest_user_line(prompt: str) -> str:
    """Extracts the most recent 'user: ...' turn from a conversation-style
    prompt (see conversation.py's _build_extraction_prompt), falling back
    to the whole prompt if it isn't in that format — keeps the mock
    adapter honest about what it's actually "understanding" rather than
    echoing internal instruction text back as the user's raw query."""
    for line in reversed(prompt.splitlines()):
        if line.startswith("user: "):
            return line[len("user: ") :].strip()
    return prompt.strip()


class MockAIAdapter:
    """Deterministic fallback — no ML, no network. Keeps text discovery
    usable when Gemini is disabled; never fakes a Live connection."""

    async def generate_text(self, prompt: str, *, response_schema: type[T]) -> T:
        if response_schema is not TravelerContext:
            raise AdapterUnavailableError("Mock AI adapter only supports TravelerContext extraction.")
        raw_query = _latest_user_line(prompt)
        words = re.findall(r"[a-zA-Z']+", raw_query.lower())
        interests = [w for w in words if w not in _STOPWORDS and len(w) > 2][:6]
        context = TravelerContext(raw_query=raw_query, interests=interests)
        return context  # type: ignore[return-value]

    async def issue_live_token(self) -> LiveTokenIssueResult:
        raise AdapterUnavailableError("Gemini Live voice is not configured on this server.")


def _translate_sdk_error(exc: Exception) -> Exception:
    if isinstance(exc, genai_errors.ClientError):
        if exc.code == 429:
            return AdapterRateLimitedError(str(exc))
        return AdapterUnavailableError(str(exc))
    if isinstance(exc, (genai_errors.ServerError, TimeoutError, ConnectionError)):
        return AdapterUnavailableError(str(exc))
    return AdapterUnavailableError(str(exc))


class GeminiAIAdapter:
    """Real Gemini adapter — google-genai SDK, self-paced with
    IntervalRateLimiter (same pattern as the Phase 4 location adapters,
    see docs/DECISIONS.md ADR-030), but the SDK owns HTTP/transport
    directly rather than going through the shared httpx client."""

    def __init__(self, settings: Settings, tool_declarations: list[dict[str, object]]) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._limiter = IntervalRateLimiter(settings.gemini_min_interval_seconds)
        self._tool_declarations = tool_declarations

    async def generate_text(self, prompt: str, *, response_schema: type[T]) -> T:
        await self._limiter.wait()
        try:
            response = await self._client.aio.models.generate_content(
                model=self._settings.gemini_model_text,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_gemini_safe_schema(response_schema),
                ),
            )
        except genai_errors.APIError as exc:
            raise _translate_sdk_error(exc) from exc
        except (TimeoutError, ConnectionError) as exc:
            raise AdapterUnavailableError(str(exc)) from exc

        # A raw-dict response_schema (unlike passing the Pydantic class
        # directly) opts out of the SDK's own auto-parsing, so we validate
        # the returned JSON text against the real model ourselves.
        if not response.text:
            raise AdapterNoResultError("Gemini returned no parseable structured result.")
        try:
            return response_schema.model_validate_json(response.text)
        except Exception as exc:
            raise AdapterNoResultError("Gemini returned an invalid structured result.") from exc

    async def issue_live_token(self) -> LiveTokenIssueResult:
        now = datetime.now(UTC)
        expire_time = now + timedelta(seconds=self._settings.gemini_live_token_ttl_seconds)
        session_expire_time = now + timedelta(seconds=self._settings.gemini_live_session_ttl_seconds)

        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=str(decl["name"]),
                            description=str(decl["description"]),
                            parameters=decl["parameters"],  # type: ignore[arg-type]
                        )
                        for decl in self._tool_declarations
                    ]
                )
            ],
            system_instruction=types.Content(
                parts=[types.Part(text=LIVE_SYSTEM_INSTRUCTION)]
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            ),
        )

        try:
            token = await self._client.aio.auth_tokens.create(
                config=types.CreateAuthTokenConfig(
                    uses=1,
                    expire_time=expire_time,
                    new_session_expire_time=session_expire_time,
                    live_connect_constraints=types.LiveConnectConstraints(
                        model=self._settings.gemini_model_live,
                        config=live_config,
                    ),
                    lock_additional_fields=["tools", "system_instruction"],
                )
            )
        except genai_errors.APIError as exc:
            raise _translate_sdk_error(exc) from exc
        except (TimeoutError, ConnectionError) as exc:
            raise AdapterUnavailableError(str(exc)) from exc

        return LiveTokenIssueResult(
            token=token.name or "",
            expire_time=token.expire_time or expire_time,
            new_session_expire_time=token.new_session_expire_time or session_expire_time,
            model=self._settings.gemini_model_live,
        )


__all__ = ["AIAdapter", "GeminiAIAdapter", "LIVE_SYSTEM_INSTRUCTION", "LiveTokenIssueResult", "MockAIAdapter"]
