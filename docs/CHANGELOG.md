# LocaLens — Changelog

> All notable changes to LocaLens are documented here.
> Format: [Phase] [Date] — Description
> Ordered: most recent first.

---

## [Unreleased] 2026-09-27 — Task 4 What-if Itinerary Simulation

- Added typed scenario, baseline, evidence, impact, alternative, and response contracts plus a `DomainIntelligenceProvider` extension protocol with a mock only. No Nugen runtime or database migration was added.
- Added authenticated `POST /api/v1/digital-twin/itineraries/{id}/simulate` for a read-only, bounded preview and `POST /api/v1/digital-twin/simulations/{id}/apply` for a version-checked traveler-approved apply through the existing `ReplanningService`.
- Reused current weather, OSRM routing, area-level social context, and discovery/ranking services; bounded requests and alternatives. Hypothetical inputs and advisory social evidence remain labelled, and unavailable route geometry is not fabricated.
- Added the traveler-facing what-if panel, impact annotations on the existing itinerary map, and a read-only voice `simulate_what_if` tool. The preview cache is process-local, capped at 256 entries, and expires after 15 minutes.
- Verification in the Desktop project: backend pytest **463 passed**; frontend Vitest **103 passed**; `npx tsc --noEmit`, changed-file ESLint, Task 4 Ruff, and strict mypy on changed modules passed. Webpack production build (`npm run build -- --webpack`) passed.
- Repository-wide checks still report existing findings in unrelated files: Ruff **367**, strict mypy **152**, and ESLint **3 errors + 2 warnings**. Default Turbopack build initially failed when the existing Google Font fetch was blocked; Webpack build passed after network permission was granted. Live itinerary workflow verification still requires an authenticated traveler session.
- Live smoke check: the existing Discover page rendered its MapLibre/OpenFreeMap map with attribution; the local API health endpoint returned 200 and OpenAPI exposed both Task 4 endpoints. The authenticated itinerary preview/apply flow remains unverified in the browser because the current session is logged out.
- Existing discovery/map/routing/weather/social behavior is preserved. No GPS tracking or additional social ingestion was introduced.

## [Unreleased] 2026-09-27 — Additive Public Social Signal Context (Task 3)

- Added a backend Bluesky adapter using the official `app.bsky.feed.searchPosts` contract, deterministic topic classification, normalized internal signals, time decay, deduplication, corroboration counts, and bounded aggregate caching.
- Added authenticated `GET /api/v1/twin/social-signals`. Responses contain area-level aggregate clusters only; no post text, account identifiers, URLs, or raw provider payloads are returned. No database migration or durable social data storage was added.
- Added an explicit Social Pulse control and accessible aggregate panel to the existing itinerary map. It calls the typed API only when enabled, cancels stale requests, and labels the selected search center as area-level context rather than a post location.
- Added opt-in topic and time-window filters, a local severity filter, qualitative heuristic-confidence bands, and explicit update age. The API validates the requested lookback window.
- Social signals remain advisory and do not change itinerary, safety, feasibility, weather, or replanning decisions. A future Nugen interpreter interface is present without a Nugen dependency or pipeline change.
- Verification: API suite 457 passed; frontend Vitest 101 passed; changed-file Ruff/mypy, ESLint, and TypeScript checks passed. Repository-wide ESLint still reports 3 errors and 2 warnings in untouched files. `next build` previously failed fetching the existing Google Font; official Bluesky search returned HTTP 403, and the already-running API process did not load the new route.
- Manual live UI verification remains pending until the local API is restarted. Existing MapSurface, routing, weather, and discovery behavior are preserved.

## [Unreleased] 2026-09-27 — Additive Itinerary Geospatial Visualization

- Extended the existing MapLibre `MapSurface` with optional clustered annotations, numbered/selected/affected/locked styling, explicit focus, bounds fitting, and additional route geometries. Existing discovery markers and route props remain supported.
- Added an itinerary map using only coordinates already present on itinerary experience/custom activity records. Map selection and timeline selection share React state; missing coordinates stay visible in the text timeline but are not inferred.
- Added explicit, sequential route geometry loading through the existing typed `/api/v1/location/route` client, with per-session leg caching and cancellation. Only successful OSRM line geometry is drawn; estimates and failures are described as unavailable geometry.
- Added selected-stop weather through the existing normalized context API and explicit nearby POI exploration through the existing location API. Weather labels distinguish LIVE, CACHED, STALE, MOCK, and UNAVAILABLE. No weather tile endpoint or overlay was enabled because this archive contains no weather tile adapter/configuration or verified tile account capability; the base map works unchanged.
- No backend endpoint or database migration was added.
- Verification: frontend Vitest **98/98**, `npx tsc --noEmit` and changed-file ESLint passed; `npm run build -- --webpack` passed. Default Turbopack build could not bind a local port in the sandbox, so the supported Webpack builder was used. Repository-wide ESLint still reports 3 existing errors and 2 warnings in untouched files. Backend pytest **450 passed**. Repository-wide Ruff reports 371 existing findings and `mypy --strict src` reports 152 existing typing findings; this feature changes no backend files. Manual credentialed trip/map smoke testing was unavailable because this archive has no configured API/database environment or credentials.

## [Unreleased] 2026-09-27 — Traveler Weather Context Add-on

- Added an authenticated, bounded normalized weather forecast endpoint alongside the existing current-weather endpoint. Provider errors remain generic at the API boundary, and forecast coordinates come from the validated request location.
- Added a compact weather card to saved traveler itineraries using the first stop with verified coordinates. It labels live, cached, stale, mock, and unavailable data explicitly; it does not request device location.
- Started the existing context monitor once during FastAPI lifespan only when live weather is configured, connected its callback to the existing replanning service, and stop it cleanly at shutdown. Mock weather never triggers automatic replanning.
- Added API, monitor lifecycle, and frontend weather presentation tests. No migration or itinerary model changes were required.

## [Unreleased] 2026-09-25 — Phase 12 Final Verification Attempt

Attempted full Phase 12 production integration, testing, hardening, and deployment.
- **Completed locally**: `apps/api/Dockerfile`, `render.yaml`, and `vercel.json` configurations created. All backend tests (`368/368`), frontend lint/tsc/vitest/build passed. Architectural isolation confirmed.
- **Blocked**: Production deployment (Docker missing locally, Postgres missing, no real cloud credentials for Supabase/Vercel/Render, no Playwright setup).
- Phase 12 is marked as **BLOCKED** and not claimed as Complete.

## [Unreleased] 2026-09-25 — Phase 0-9 Reconciliation: Static Analysis, Live API Smoke Tests, Test-Coverage Gap Fix

A full-codebase reconciliation pass — not a new feature phase. Ran `mypy --strict`/`ruff` across
the backend, live smoke tests against real Gemini/OpenWeather/Ticketmaster credentials, and a
full pytest + frontend (`tsc`/`eslint`/`vitest`/`next build`) verification pass, to establish the
actually-verified state of the app independent of what earlier phase docs claimed. Full findings
and rationale: `docs/DECISIONS.md` ADR-055.

### Fixed — real bugs found via static analysis / live verification

- **Ranking budget filter never applied** (`src/services/ranking.py`) — read
  `context.constraints.budget_max` (a shape that doesn't exist on `TravelerContext`) instead of
  the flat `context.budget_max` field; the budget penalty silently never fired. Found by mypy.
- **API keys leaking into plaintext server logs** (`src/core/logging.py`) — httpx's `%s`-template
  logging stores the real URL in `record.args`, not `record.msg`; a filter that only inspected
  `record.msg` missed OpenWeather's `appid=`/Ticketmaster's `apikey=` querystring values. Fixed
  with a `_RedactSecretsFilter` using `record.getMessage()`, attached directly to
  `logging.getLogger("httpx")`. Verified live against real API calls: keys now redacted in logs.
- **Replanning crash on offset-naive/aware datetime comparison, plus a sequence_order collision**
  (`src/services/replanning.py`) — SQLite strips tzinfo on round-trip; `ReplanningService`
  compared naive DB values directly against aware `now`, crashing with `TypeError`. Fixed via
  local aware-conversion closures. A second, independent bug: kept items and newly-composed items
  both numbered `sequence_order` from 1, causing `IntegrityError: UNIQUE constraint failed`; fixed
  via offsetting new items past the kept count and a two-phase renumber for kept items (SQLite
  checks UNIQUE constraints immediately, unlike Postgres's deferrable constraints).
- **Unvalidated stored conversation context crashes tool-call ranking** (`src/api/v1/conversation.py`)
  — `conversation.latest_traveler_context` (a raw dict) was passed unvalidated into the ranking
  pipeline; reproduced live as `AttributeError: 'dict' object has no attribute 'budget_max'`.
  Fixed with `TravelerContext.model_validate(...)`. New regression test added and confirmed to
  fail against a temporary revert before confirming the fix.

### Fixed — test infrastructure

- **Vacuous test coverage**: `tests/conftest.py`'s `discovery_dataset` fixture seeded zero
  `ExperienceOpeningHour`/`ExperienceAvailability` rows, so every test-suite compose call returned
  `feasible_count: 0` and ~15+ tests' `if "items" not in body: return` guards silently no-op'd
  instead of asserting anything. Fixed by seeding real opening-hours and a two-year availability
  window in the fixture — those tests now genuinely exercise their intended logic.
- **SSE TestClient hang**: `tests/test_itinerary_sse.py`'s owner-connects test hung indefinitely
  reading the endpoint's intentionally-infinite `while True` SSE stream through Starlette's
  in-process ASGI TestClient transport (confirmed not an app bug — the real endpoint works
  correctly via live curl). Rewritten to invoke the route's real ownership-check +
  `StreamingResponse` construction directly, without opening a TestClient stream.
- `session.get(Itinerary, id)` in `tests/test_replanning.py` doesn't eager-load `.items`, causing
  `MissingGreenlet` on later access; fixed via an explicit `selectinload` helper.

### Verified (real runs, not assumed)

- Backend: `python -m pytest -q` → **361 passed, 0 failed, 0 hangs, 65.06s**.
- Frontend: `tsc --noEmit` clean, `eslint` clean, `vitest run` → **56/56 passed (7 files)**,
  `next build` → succeeded, all 15 routes compiled (11 static, 4 dynamic/server-rendered).
- Live API calls re-confirmed working post-fix: Gemini structured output, OpenWeather, and
  Ticketmaster all return real (non-fallback) data, with API keys now redacted in logs.
- Security sweep: no hardcoded API keys/secrets found in tracked source; root `.env` confirmed
  untracked by git (not present in `git ls-files`).
- PostgreSQL: **NOT VERIFIED** — no Postgres instance available in this environment; all
  verification above ran against the dev SQLite database.

### Deferred (assessed safe, intentionally not fixed — see ADR-055)

- `ranking.py:140` dict-unpacking mypy variance warning constructing `RankedExperienceItem` —
  safe at runtime, deferred as a larger refactor than this reconciliation's minimal-fix scope.
- ~18 mypy "Item None of Traveler | None" warnings across `bookings.py`/`feedback.py`/
  `itineraries.py`/`recommendations.py` at `user.traveler.id` — verified safe because
  `UserRepository._base_query()` always eager-loads `User.traveler`, so it's never `None` for a
  traveler-role user at runtime.
- The two conflicting naive-datetime conventions (UTC-implied vs. local-Kolkata-implied) remain
  unresolved by design; this pass only fixed the crash sites it touched.

---

## [Unreleased] 2026-09-25 — Live Debugging Session: Deployment Fixes + Composer Correctness

Fixes found and corrected while running the deployed app end-to-end for the first time — the
first real browser/traveler-flow exercise since Phase 8/9 were built. None of these were caught
by the automated test suite because they only manifest against a genuinely running dev server,
seeded data, and a real browser (hydration, browser extensions, Windows networking, DevTools
inspection). All fixes verified: backend 360/360 tests still passing throughout, frontend
tsc/eslint/vitest clean.

### Fixed — Environment / configuration

- `JWT_ACCESS_SECRET` / `JWT_REFRESH_SECRET` set to an *empty string* (not unset) in `.env` —
  pydantic-settings treats an explicit empty string as a real value, overriding the working
  dev-only default secrets, so every login/register call failed with
  `jwt.exceptions.InvalidKeyError: HMAC key must not be empty.`. Same root cause as an earlier
  `COOKIE_SECURE=` fix — omit the var entirely rather than leaving it blank.
- `GEMINI_MODEL_TEXT=gemini-3.8-flash` returned a persistent `503 RESOURCE_EXHAUSTED`/"high
  demand" from Google's API (likely limited preview-tier capacity on this account) — switched to
  `gemini-2.5-flash`, verified working immediately.
- `NEXT_PUBLIC_API_BASE_URL` in the root `.env` was never actually read by the Next.js dev
  server — Next.js only loads `.env`/`.env.local` from its own package directory
  (`apps/web/`), not a monorepo root. Documented; a local `apps/web/.env.local` override was used
  during debugging.

### Fixed — Gemini structured output

- `TravelerContext`'s `response_schema` (passed directly to Gemini's structured-output API) used
  Pydantic `gt=0` (emits `exclusiveMinimum`) on three fields and `extra="forbid"` (emits
  `additionalProperties: false`, including on the nested `CommittedTimeBlock` list) — both are
  JSON Schema keywords Gemini's schema endpoint rejects outright
  (`400 INVALID_ARGUMENT: Unknown name "additional_properties"`), so every real conversational
  turn failed and silently fell back to keyword-only discovery. Fixed by relaxing the three
  fields to `ge=0` and adding `_gemini_safe_schema()` in `src/adapters/ai.py`, which recursively
  strips `additionalProperties` from any schema before sending it to Gemini, then validates the
  raw response text against the real Pydantic model directly (`response.text` +
  `model_validate_json`, rather than relying on the SDK's own auto-parse of the class, which
  requires passing the class unmodified).

### Fixed — Frontend

- `MapLibre` (v6) never painted tiles — controls rendered, but zero real tile network requests
  ever fired. Root cause (two-part): (1) MapLibre's render worker is loaded via
  `import.meta.url`-relative resolution, which Turbopack's dev server 404s; fixed by copying the
  worker bundle into `public/maplibre/` and calling `setWorkerUrl()`. (2) That worker bundle
  itself `import`s a sibling `maplibre-gl-shared.mjs` from the same `node_modules` directory —
  only the worker file was copied initially, so the worker died silently on its own internal
  import the moment it started (no error surfaced anywhere; the main thread kept firing
  optimistic `dataloading` events forever). Fixed by copying both files; documented the
  dependency in code so a future `maplibre-gl` version bump doesn't silently reintroduce this.
- Voice transcript panel showed only the last few words of a longer Gemini reply — Gemini Live
  streams `inputTranscription`/`outputTranscription` as incremental delta chunks, not cumulative
  text, and the merge logic in `useVoiceAgent.ts` replaced the previous line with each new chunk
  instead of concatenating. Fixed to append; panel also now wraps long lines instead of clipping.
- `AuthContext.tsx`'s bootstrap effect used a `bootstrapped` ref to guard against a duplicate
  `/auth/refresh` call, which interacted badly with React Strict Mode's dev-only
  mount→cleanup→mount cycle: the *first* invocation's cleanup set its own `cancelled` flag to
  `true`, then the ref made the *second* invocation a no-op — so the only bootstrap call that
  ever actually ran was guaranteed to see `cancelled === true` by the time its (successful)
  network request resolved, permanently skipping `setIsLoading(false)`. Every fresh full-page
  load of a `RequireRole`-gated page (Trips/Saved/Provider) hung on the loading skeleton forever,
  even though the request itself succeeded. Fixed by removing the ref so each Strict Mode
  invocation gets its own independent cancellation flag (Strict Mode is dev-only; the tradeoff is
  one harmless duplicate refresh call in development).
- `client.ts` surfaced FastAPI 422 validation errors as the generic `"Validation failed"` string
  instead of the real per-field reason already present in the response `detail` array (e.g. a
  password under 8 characters). Added `describeValidationError()` to build a readable message
  from the actual `detail` entries; also added client-side password-length/business-name checks
  to the register form so the same mistake fails fast without a round-trip.
- `ItineraryComposerForm.tsx` showed the generic backend `"The composed itinerary failed
  validation."` message on any composition failure, discarding the real `candidate_count` /
  `feasible_count` / per-issue `reasons` the API already returns. Added
  `describeCompositionFailure()` to build an explanatory message from that real data (e.g. "Found
  7 matching experiences, but the best available option isn't open during your chosen time
  window.") — every claim traces back to actual response data, nothing invented.
- `ItineraryNarratorService`'s fact prompt included `booking_status=not_requested` for every
  single item regardless of whether anything had happened, so Gemini (correctly, per its
  instructions to narrate only supplied facts) wrote a repetitive "booking is currently not
  requested" line on every item narration. Fixed to omit the `booking_status` fact entirely when
  there is no actual request, and instructed Gemini accordingly — booking is now only mentioned
  when there's something real to say.

### Fixed — Demo data completeness (not a code bug, but blocked every real feature test)

- Zero `ExperienceEmbedding` rows existed in the dev database — nobody had ever run
  `scripts/index_embeddings.py` against it, so semantic search/composition had nothing to
  retrieve against. Ran it (341/353 embedded; 12 hit the Gemini free-tier rate limit and were
  correctly left un-embedded rather than faked).
- Zero `ExperienceAvailability` rows existed anywhere in the catalog — the itinerary composer
  always supplies a date/time window, which makes availability a hard blocking constraint per
  Phase 6's "never assume bookable without evidence" policy, so composition could never succeed
  against this seed data. Added `scripts/seed_availability.py` (new, idempotent) to derive
  realistic bookable slots from each experience's real recorded opening hours (810 slots across
  65 experiences with real hours; the other 288 experiences have no opening-hours data at all and
  honestly stay UNKNOWN — never fabricated). Labeled as synthetic demo data throughout, never
  presented as real provider-supplied availability.

### Fixed — Feasibility / composer correctness (real logic bugs, not just missing data)

- `FeasibilityService._check_opening_hours` / `_check_availability` required an experience's
  opening hours/availability slot to fully *contain* whatever time window was supplied. Correct
  for verifying one specific visit, but the itinerary composer's whole-day candidate gate passed
  the traveler's entire requested window (e.g. 9am–6pm) into the same check, which then required
  every candidate to be open for the *entire* day — a bar almost no real venue with partial-day
  hours can clear, blocking composition against nearly the whole catalog. Added a
  `precise_window` distinction: a date-only constraint (no specific start/end — the composer's
  gate, before any slot is chosen) now checks for *any overlap* that day; a precise start/end
  (single-experience verification, and the mandatory post-composition per-item re-check) keeps
  the original strict containment semantics unchanged.
- `scripts/seed_availability.py`'s first version stored local wall-clock datetimes without
  converting to UTC first; SQLite drops tzinfo on write regardless, and
  `FeasibilityService._as_aware` treats a naive stored value as UTC per the model's documented
  convention — so every seeded slot was silently offset by the timezone difference (+5:30).
  Fixed to convert to UTC before storage; re-seeded.
- The Phase 8 composer's post-composition validator correctly re-checks each item's precise
  feasibility at its actual scheduled slot and correctly rejects a bad assignment, but nothing
  ever retried — composition failed outright on the very first per-item rejection even when other
  feasible candidates existed, despite the originally-specced "bounded deterministic
  alternatives" behavior never having been implemented. Added a bounded retry loop in
  `compose_itinerary.py` (`Settings.composer_max_validation_retries`, default 5): on a specific
  `EXPERIENCE_NOT_FEASIBLE` rejection, that one experience is excluded from the candidate pool and
  composition is retried from scratch, converging on a valid plan when one exists among the
  remaining feasible candidates.
- Verified end to end: a real compose request now returns a complete, valid, Gemini-narrated
  multi-stop Mumbai itinerary with correct chronological scheduling, real OSRM travel times, and
  budget compliance.

### Note on Phase 9 documentation

The Phase 9 commit updated `docs/AI_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
`docs/PROJECT_STATE.md`, and `docs/TASKS.md`, but this `CHANGELOG.md` entry for Phase 9 itself
was missed — see the entry immediately below, added retroactively.

---

## [Phase 9] 2026-09-24 — Real-Time Context + Events + Dynamic Replanning

Real-time weather/event context, deterministic impact detection, dynamic itinerary replanning,
and live SSE update delivery — built entirely on top of the existing Phase 6/7/8 pipeline, never
duplicating retrieval, feasibility, ranking, or composition. See `docs/PROJECT_STATE.md`'s Phase 9
section for the full implementation detail (adapters, models, API surface, test counts); summary:

- Real `OpenWeatherAdapter` and `TicketmasterEventAdapter` implementations (replacing the Phase 0
  placeholder stubs), each with a mock/seed fallback, TTL caching, and rate limiting matching the
  existing OSRM/Nominatim adapter pattern.
- `WeatherImpactService` / `ContextImpactService` — deterministic-only (no LLM) verdicts on
  whether a context change materially affects an itinerary, with hysteresis to prevent
  GOOD→CAUTION→GOOD oscillation.
- `ReplanningService` — re-runs the existing Phase 6 retrieval+feasibility, Phase 7 ranking, and
  Phase 8 composition/validation against only the remaining, unlocked, incomplete portion of an
  itinerary; completed and explicitly-locked items are never rewritten.
- Itinerary versioning/revisions with optimistic-locking conflict detection
  (`ITINERARY_VERSION_CONFLICT`) and idempotency-key support.
- `GET /api/v1/itineraries/{id}/updates` — SSE live plan updates, ownership-checked.
- `replan_experience` — the fourth and final Gemini tool; requests backend replanning only, never
  mutates the itinerary or supplies traveler_id itself.
- Backend: 360/360 tests passing (298 pre-Phase-9 baseline + 62 new). Frontend: 56/56 tests
  passing, clean `tsc`/ESLint/`next build`.
- **NOT VERIFIED**: live OpenWeather/Ticketmaster API calls (no keys in the isolated build
  environment) and PostgreSQL (no instance available) — same honesty convention used by every
  prior phase in this project for its own unverifiable pieces.

---

## [Phase 8] 2026-09-24 — Deterministic Itinerary Composition with Gemini Narrative Generation

### Phase 7 preflight fixes (found and fixed before Phase 8 work began)

`POST /api/v1/recommendations` and the `search_experiences`/`compose_experience` conversational
tool path were both completely broken end-to-end prior to this session — no existing test exercised
either path with a real ranked candidate set. Fixed:

- `get_embedding_adapter`/`get_routing_adapter` (both no-argument `lru_cache` singletons) were being
  called with a `Settings` argument in three call sites (`src/api/v1/recommendations.py`,
  `src/api/v1/conversation.py`, `src/services/ai_tools.py`) — `TypeError: unhashable type: 'Settings'`
  on every call
- `DiscoveryPipelineService.run_with_ranking` accessed `self._retrieval.session` (a private attribute
  that doesn't exist as public) — `AttributeError` on every ranked call
- `WeightedPersonalizedRanker` built `RankedExperienceItem` from the wrong/incomplete field set
  (referenced a non-existent `Experience.slug`, was missing several schema-required fields such as
  `short_description`/`currency`/`is_price_estimated`) — crashed on every real ranking pass
- `PersonalizedRankingService.rank` constructed `TravelerContext()` with no `raw_query`, which is a
  required field — crashed whenever no conversational context was available (i.e. every direct
  `/recommendations` call)
- `RecommendationResponse.excluded_summary` expected `ExcludedReasonSummary` (Pydantic) but the
  pipeline produced a different `ExcludedSummary` dataclass — `ValidationError` on every response
- `discovery_dataset` test fixture never seeded `ExperienceEmbedding` rows, so semantic retrieval
  legitimately (and silently) returned zero candidates for two existing Phase 5/6 tests
- Existing SQLite `alembic upgrade head` was broken outright (`op.drop_constraint` outside batch
  mode is unsupported on SQLite) — fixed by wrapping in `op.batch_alter_table` and enabling
  `render_as_batch` for the SQLite dialect in `alembic/env.py` (PostgreSQL behavior unchanged)
- Added `tests/test_pipeline_single_execution.py` — the required regression proof that retrieval and
  feasibility each execute exactly once per logical request, for both the direct
  `/recommendations` endpoint and the conversational `search_experiences` tool path

All 250 pre-existing backend tests passed after these fixes, before any Phase 8 code was written.

### Added — Backend

- `Itinerary`, `ItineraryItem`, `BookingRequest` models (`src/models/itinerary.py`,
  `src/models/itinerary_item.py`, `src/models/booking_request.py`) and Alembic migration
  `8a004268dcb0_phase8_itinerary_composer` (verified against fresh SQLite; up/down/up round-trip
  verified; **PostgreSQL path NOT VERIFIED — no PostgreSQL instance available**)
- `ExperienceComposerService` (`src/services/experience_composer.py`) — deterministic two-stage
  composition (greedy selection + bounded local-improvement pass), no external optimizer; never
  recomputes Phase 7 `ranking_score` (see docs/DECISIONS.md ADR-045)
- `ItineraryValidatorService` (`src/services/itinerary_validator.py`) — mandatory post-composition
  validation reusing `FeasibilityReasonCode` (extended with itinerary/schedule-specific codes); runs
  before any narrative or persistence (see ADR-046)
- `ItineraryNarratorService` (`src/services/itinerary_narrator.py`) — Gemini narrative generation via
  the existing `AIAdapter`, facts-only prompt, anti-hallucination system instruction, deterministic
  template fallback on any Gemini failure (see ADR-047)
- `compose_itinerary.py` — orchestrates the full pipeline (retrieval -> feasibility -> ranking ->
  composition -> validation -> narrative -> persist) for both the HTTP endpoint and the
  `compose_experience` tool, guaranteeing they never diverge in ordering
- `compose_experience` Gemini tool (`COMPOSE_EXPERIENCE_DECLARATION`/`execute_compose_experience` in
  `src/services/ai_tools.py`) — reuses a new `ConversationSession.last_search_candidates` cache so it
  never re-runs the Phase 6+7 pipeline redundantly when a candidate context already exists (see
  ADR-048); added to the Live tool allowlist and system instruction
- `ItineraryRepository`, `ItineraryItemRepository`, `BookingRequestRepository`
- `src/api/v1/itineraries.py` — `POST /api/v1/itineraries/compose`, `GET /api/v1/itineraries`,
  `GET /api/v1/itineraries/{id}`, `POST /api/v1/itineraries/{id}/items`,
  `DELETE /api/v1/itineraries/{id}`
- `src/api/v1/bookings.py` — `POST /api/v1/itineraries/{itinerary_id}/booking-requests`,
  `GET /api/v1/bookings/me`, `GET /api/v1/provider/booking-requests`,
  `PATCH /api/v1/provider/booking-requests/{id}`, `POST /api/v1/bookings/{id}/cancel`. REQUESTED
  intent only — `BookingRequestStatus` has no `CONFIRMED` value and no payment field exists anywhere
  on the model/schema/API surface
- `src/schemas/itinerary.py`, `src/schemas/booking.py`
- Config: `composer_default_max_experiences`, `composer_max_candidates`,
  `composer_max_optimization_iterations`, `composer_min_buffer_minutes`,
  `composer_default_travel_mode`, `composer_narrative_model_version`,
  `composer_template_narrative_version`
- Tests: `test_experience_composer.py` (8), `test_itinerary_validator.py` (10),
  `test_itinerary_narrator.py` (7), `test_compose_experience_tool.py` (6),
  `test_itinerary_api.py` (9), `test_booking_api.py` (8) — all passing, no live Gemini/network calls

### Added — Frontend

- `lib/api/itineraries.ts`, `lib/api/bookings.ts` — typed fetch wrappers matching the existing
  `lib/api/feasibility.ts`/`recommendations.ts` pattern, exported through `lib/api/index.ts`
- `lib/itinerary/itineraryDisplay.ts` — pure display helpers (booking status label/tone, travel gap
  text, cost formatting); 15 passing unit tests in `itineraryDisplay.test.ts` (matches the Phase 6
  `feasibilityDisplay.test.ts` precedent) — explicitly asserts REQUESTED/ACCEPTED are never labelled
  "Confirmed"
- `ItineraryComposerForm`, `BookingRequestButton`, `RealItineraryTimeline`, `TripComposerSection`
  components; wired into `/trip`, gated behind the existing `RequireRole` auth guard
- Fixed two genuine pre-existing Phase 7 defects blocking a clean `tsc --noEmit`/`next build`:
  `lib/api/recommendations.ts`/`lib/api/feedback.ts` imported a `fetchApi` export that
  `lib/api/client.ts` never provided (only `apiClient`); `types/experience.ts`'s `Experience` type
  was missing the `matchSignals`/`personalized` fields the Phase 7 adapter already populated

### Verification

- Backend: `pytest -q` — **298 passed**, 0 failed (250 pre-existing + 48 new Phase 8 tests)
- Backend: `alembic upgrade head` against a fresh SQLite DB — verified clean; up/down/up round-trip
  verified; PostgreSQL explicitly **NOT VERIFIED** (no PostgreSQL instance available)
- Frontend: `npx tsc --noEmit` — clean; `npm run lint` — clean; `npx vitest run` — **51 passed**
  (6 files); `npm run build` — succeeds
- Real (live, network) Gemini narrative generation: **NOT VERIFIED in this session** — the
  root `.env`'s `GEMINI_API_KEY` is not reachable from this worktree without copying the secret file
  into the worktree, which this session's permission model correctly blocked as credential
  materialization; the narrator's Gemini call path mirrors the exact Phase 5/6
  `generate_text(..., response_schema=...)` pattern already exercised by passing tests elsewhere in
  this repo, and the fallback path is fully tested, but no live API round-trip was made

---

## [Phase 6] 2026-09-23 — Semantic Retrieval + Deterministic Feasibility Engine

### Added

- `EmbeddingAdapter` interface (`src/adapters/embedding.py`) — `GeminiEmbeddingAdapter`
  (`google-genai` SDK, `gemini-embedding-2`, asymmetric query/document prompting,
  **NOT VERIFIED live — no API key available**) and `MockEmbeddingAdapter` (deterministic
  hash/token-feature vector, not random). Selected by the same `GEMINI_ENABLED`+key rule as
  the Phase 5 `AIAdapter` (`src/core/embedding.py`)
- `ExperienceEmbedding` model (`src/models/embedding.py`) and Alembic migration
  `6762a731d1f1_experience_embeddings` — portable JSON column on SQLite; dialect-branched
  pgvector column + HNSW cosine index on PostgreSQL (**pgvector path NOT VERIFIED live — no
  PostgreSQL instance available**)
- Canonical text builders (`src/services/embedding_text.py`) — document text from real stored
  fields only; query text limited to semantic-intent fields (never hard constraints)
- `scripts/index_embeddings.py` — idempotent embedding backfill/refresh script with
  `--limit`/`--force`/`--dry-run`/`--only-missing` flags and per-record failure isolation
- `SemanticRetrievalService` (`src/services/semantic_retrieval.py`) — query → embed →
  candidates → SAFE deterministic pre-filters only → pool. Honest `retrieval_mode` reporting:
  `pgvector_semantic` (not verified live) / `sqlite_python_semantic` (verified) /
  `keyword_fallback` (reuses the Phase 4 discovery service)
- `FeasibilityService` (`src/services/feasibility.py`) — 100% deterministic, zero LLM calls.
  Active status, budget, duration, distance, travel time, total time, opening hours
  (timezone-aware, overnight-window-aware), availability, capacity, accessibility, and
  itinerary-conflict checks. Tri-state FEASIBLE/INFEASIBLE/UNKNOWN verdict; UNKNOWN can never
  become FEASIBLE
- Centralized reason-code enum (`src/core/feasibility_reasons.py`)
- `DiscoveryPipelineService` (`src/services/discovery_pipeline.py`) — retrieval → feasibility
  hard gate → only FEASIBLE items returned, plus an excluded-candidate reason summary
- `POST /api/v1/experiences/semantic-search` and `POST /api/v1/feasibility/check` endpoints
- `check_feasibility` — the second Gemini tool, alongside `search_experiences`. Backend-owned
  execution only; its argument schema has no field for price/hours/capacity/availability, so
  Gemini cannot supply an invented value for any of them
- Live system instruction now actually attached to `LiveConnectConfig` (closes a gap where
  Phase 5's ADR-037 documented this policy but the adapter had not yet wired it into the SDK
  call); explicitly restricts the model to the two real tools and forbids phrasing UNKNOWN as
  reassuring
- `TravelerContext` extended with optional, nullable Phase 6 fields (budget, time context,
  travel constraints, accessibility, existing commitments) — strictly additive
- Frontend: Phase 6 TypeScript types (`types/api.ts`), an API client (`lib/api/feasibility.ts`),
  and pure display-mapping functions with unit tests (`lib/feasibility/feasibilityDisplay.ts`)
- 74 new backend tests (246 total), 15 new frontend tests (35 total)

### Changed

- `Experience` model gained an `availability_slots` relationship (back-populating
  `ExperienceAvailability.experience`) and an `embedding` relationship, so
  `FeasibilityService`/`ExperienceRepository` can eager-load availability without a second
  query pattern
- `ExperienceRepository`'s base query now eager-loads `availability_slots`
- `handle_text_turn` routes through `DiscoveryPipelineService` (instead of the plain keyword
  tool) whenever the extracted `TravelerContext` carries a hard constraint — still one Gemini
  call per turn, still a deterministic templated reply

### Fixed

- `FeasibilityService`'s availability check now normalizes naive `datetime` values (SQLite does
  not round-trip `tzinfo` on `DateTime(timezone=True)` columns, unlike PostgreSQL) to UTC before
  comparison, rather than raising or silently miscomparing

### Notes

- `requirements.txt` gained `tzdata` — required for `zoneinfo` timezone lookups to work at all
  on platforms without system tzdata (observed on this Windows dev environment; also relevant
  to minimal Linux containers)
- Real Gemini embedding generation and the PostgreSQL/pgvector retrieval path are explicitly
  **NOT VERIFIED** in this environment (no API key, no Postgres instance) — implemented and
  unit-tested against documented interfaces/SQL only; see docs/PROJECT_STATE.md for the full
  IMPLEMENTED vs PARTIAL breakdown

---

## [Phase 5] 2026-09-22 — Conversational AI + Gemini Live Voice Agent

### Added — AI core (`apps/api/`)

- `src/adapters/ai.py` — real `GeminiAIAdapter` (`google-genai` SDK: `generate_content` with
  Pydantic `response_schema` for structured extraction, `auth_tokens.create` for ephemeral Live
  tokens). `MockAIAdapter.generate_text` rewritten from a hard `NotImplementedError` to a
  graceful deterministic keyword extraction — text discovery stays usable without Gemini;
  `issue_live_token` still fails loudly, voice is never faked
- `src/core/ai.py` — `get_ai_adapter()` DI provider, mirrors the Phase 4 `location.py` pattern,
  gated on `GEMINI_ENABLED` + `GEMINI_API_KEY` presence
- `src/core/config.py` — corrected stale `gemini_model_text`/`gemini_model_live` defaults
  (`gemini-2.0-flash`/`gemini-2.0-flash-live-001` → `gemini-3.8-flash`/`gemini-3.8-live`, the
  current models per live-verified ai.google.dev docs); added `GEMINI_ENABLED`,
  `GEMINI_LIVE_TOKEN_TTL_SECONDS`, `GEMINI_LIVE_SESSION_TTL_SECONDS`,
  `GEMINI_MIN_INTERVAL_SECONDS`, `CONVERSATION_HISTORY_WINDOW`
- `src/schemas/conversation.py` — `TravelerContext` (shared by text and voice),
  `SearchExperiencesArgs`/`Result`, conversation turn/detail/create schemas, `LiveTokenResponse`

### Added — Conversation & tool execution

- `src/services/ai_tools.py` — `SEARCH_EXPERIENCES_DECLARATION` (single source of truth for the
  tool schema) + `execute_search_experiences()`, a thin wrapper around the existing
  `ExperienceDiscoveryService` — zero new search logic, the only Gemini tool this phase
- `src/services/conversation.py` — text-turn orchestration: one Gemini call per turn (structured
  extraction only), bounded recent-history window, deterministic template assistant reply
  (never a second free-form Gemini call — text prose can never fabricate result claims)
- `src/models/conversation_session.py`, `conversation_message.py` — user-owned, cascade-deleted;
  `latest_traveler_context` JSON snapshot column; transcript text only, audio never persisted
- Alembic migration `conversation sessions and messages` — verified against a fresh database and
  the existing seeded database (353 experiences / 311 providers unaffected)
- `src/api/v1/conversation.py` — `POST /conversations`, `POST /conversations/{id}/messages`,
  `GET /conversations/{id}`, `POST /conversations/{id}/tool-calls` (the voice-path bridge — the
  only place `search_experiences` actually executes). Ownership 404s (never 403s) for another
  user's conversation, matching the existing non-disclosure pattern
- `src/api/v1/auth.py` — `POST /auth/live-token`, `require_traveler`-gated; ephemeral token's
  `live_connect_constraints` locks model/tools/system instruction server-side, so a tampered
  client cannot redefine them. `GEMINI_API_KEY` never leaves the backend, never logged/persisted

### Added — Frontend voice & conversational discovery (`apps/web/`)

- `lib/voice/audioCapture.ts` + `public/worklets/pcm-capture-worklet.js` — real AudioWorklet-
  based mic capture, downsampled to 16-bit/16kHz little-endian PCM (Gemini Live's documented
  input format) — deliberately not MediaRecorder/webm
- `lib/voice/audioPlayback.ts` — 24kHz scheduled `AudioBufferSourceNode` playback queue with
  gapless scheduling and hard-stop support for barge-in/interruption
- `lib/voice/pcmResample.ts` — pure resample/encode math, extracted for unit testing since
  AudioWorkletGlobalScope can't import bundled modules
- `lib/voice/geminiLiveClient.ts` — `@google/genai` Live session wrapper: transcription
  (incremental fragment merging), the tool-call bridge to the backend (never business logic in
  the browser), session resumption + GoAway proactive reconnect, barge-in via `interrupted` signal
- `hooks/useVoiceAgent.ts`, `hooks/useTextConversation.ts`
- `components/voice/{VoiceOrb,VoiceTranscriptPanel,VoiceControlButton}.tsx`
- `lib/discovery/travelerContextToPatch.ts` — the app-controlled, deterministic translation from
  AI-extracted intent to `DiscoveryState` (never the model); `location_text` is deliberately
  never mapped to `lat`/`lng` (preserves the Phase 4 explicit-geocoding-only policy)
- `components/discovery/ConversationalDiscoveryInput.tsx` — the Phase 1 permanently-disabled mic
  button is now a real voice control; text submit now also runs a real conversational turn
- `app/discover/DiscoverExperience.tsx` — threads a `Partial<DiscoveryState>` patch callback
  through; `setDiscoveryState` itself stays private, matching the existing `onChange` pattern

### Documentation

- `data/README.md`, `docs/AI_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATE.md` —
  Phase 5 status, module ownership, AI voice architecture (§7) updated from planned to implemented
- `docs/DECISIONS.md` — ADR-033 through ADR-039 (shared TravelerContext schema, one-Gemini-call-
  per-turn text orchestration, ephemeral token + `live_connect_constraints` locking, backend-only
  tool execution boundary, Live system instruction constraints, conversation persistence model,
  Vitest introduction)

### Tests

- 30 new backend tests (172 total): AI adapter (mock + real against a fake `google-genai` SDK
  client — no real network calls), conversation service/API (ownership isolation, tool-call
  validation, unknown-tool rejection), live-token endpoint (role gate, mock-always-503,
  real-shape success) — all passing alongside `ruff`, `mypy --strict`
- Vitest newly introduced for the frontend (no prior test framework existed) — 20 tests scoped
  to pure high-risk logic: the discovery-patch translator and PCM encode/decode/resample math —
  all passing alongside `tsc --noEmit`, `eslint`, `next build` (15 routes)
- Not covered by automated tests: the real Gemini Live browser↔Google WebSocket path — requires
  a human with a working `GEMINI_API_KEY`; manual verification checklist in ADR-035

### Explicitly not implemented (deferred by design)

- Semantic search/embeddings/pgvector, ML ranking, deterministic feasibility engine, AI
  composer/itinerary generation, dynamic replanning, weather/events, provider analytics,
  booking/payments, safety backend integration, and any Gemini tool beyond `search_experiences`
  — all remain scoped to their respective later phases per docs/ROADMAP.md

---

## [Phase 4] 2026-09-22 — Experience Discovery, Catalog & OSM Location Layer

### Added — Location core (`apps/api/`)

- `src/core/http_client.py` — shared async httpx client singleton
- `src/core/cache.py` — generic `TTLCache[T]` (PEP 695 syntax)
- `src/core/rate_limit.py` — `IntervalRateLimiter` (`asyncio.Lock`-based)
- `src/core/geo.py` — portable Haversine distance, bounding-box math, coordinate validation
  (`EARTH_RADIUS_KM`) — no PostGIS/SQLite spatial extension, works identically on SQLite and
  PostgreSQL
- `src/adapters/errors.py` — typed `AdapterTimeoutError`/`AdapterRateLimitedError`/
  `AdapterUnavailableError`/`AdapterNoResultError`
- `src/adapters/geocoding.py` — real `NominatimGeocodingAdapter` (forward + reverse geocoding,
  rate-limited to ~1 req/sec, TTL-cached, descriptive User-Agent per Nominatim's usage policy)
- `src/adapters/routing.py` — real `OSRMRoutingAdapter` (route + travel-time matrix, profile
  restricted to driving/walking/cycling)
- `src/adapters/poi.py` — real `OverpassPOIAdapter` (deterministic server-built Overpass QL from
  a fixed category allowlist — never user-supplied QL)
- `src/core/location.py` — DI providers that switch to `Mock*Adapter` when
  `LOCATION_SERVICES_ENABLED=false`, so the catalog keeps working without external services
- `src/schemas/location.py`, `src/api/v1/location.py` — `GET /api/v1/location/{search,reverse,
  nearby-pois}`, `POST /api/v1/location/{route,travel-time-matrix}`
- `src/api/v1/categories.py` — `GET /api/v1/categories` (for the provider location picker)

### Added — Discovery & catalog search

- `src/repositories/experience_repository.py` — `ExperienceFilters` (keyword + bbox), `search()`
  does a bounded candidate fetch; sorting/pagination stays in Python for portability
- `src/services/discovery.py` — `ExperienceDiscoveryService`, deterministic non-personalized
  relevance scoring with documented field weights — explicitly not ML/AI
- `GET /api/v1/experiences` extended: keyword/category/price/duration/lat+lng+radius_km/sort
  filters, per-result `distance_km`/`travel_time_minutes`/`travel_time_source` enrichment
  (capped at `OSRM_MAX_MATRIX_DESTINATIONS`, always labels `osrm` vs `haversine_estimate`)

### Added — Frontend map & discovery (`apps/web/`)

- `components/common/MapSurface.tsx` — real MapLibre GL JS map (replaces the Phase 1 static
  placeholder), clustered GeoJSON experience source, origin/route sources, "Search this area"
  bounds-triggered re-query (never auto-fires on pan/zoom alone)
- `lib/config/map.ts`, `lib/geo/{haversine,geojson}.ts`, `lib/api/location.ts`,
  `types/{location,discovery}.ts`
- `lib/discovery/urlState.ts` — URL-synchronized discovery state
  (`?q=&category=&lat=&lng=&radius_km=&sort=`)
- `hooks/{useExperienceDiscovery,useUserLocation,useLocationSearch}.ts` — geolocation and place
  search are explicit-trigger only, never auto-requested
- `app/discover/DiscoverExperience.tsx` — rewritten with `LocationBar`, real map/list sync,
  mobile list/map toggle
- `components/experience/ExperienceDetail.tsx` — "Set a starting point" + "Show route" using the
  real routing adapter, labels estimated vs. OSRM-sourced travel time
- `components/provider/ExperienceForm.tsx` — location-search picker (explicit pick only)

### Documentation

- `data/README.md` §9 — Nominatim/Overpass/OSRM/MapLibre/OpenFreeMap attribution, licensing, and
  scope (source vs. renderer vs. tiles vs. geocoding vs. routing)
- `docs/DECISIONS.md` — ADR-022 through ADR-032 (Haversine portability, Nominatim/Overpass/OSRM
  usage strategy, MapLibre + OpenFreeMap, clustering, "Search this area" UX, URL state sync,
  caching/rate-limiting, `LOCATION_SERVICES_ENABLED` kill switch, location privacy)

### Tests

- 70 new backend tests (142 total): geo math, discovery service/API, adapter unit tests against
  fake HTTP clients (no real network calls in the automated suite), location API, categories —
  all passing alongside `ruff`, `mypy --strict`; frontend `lint`/`tsc --noEmit`/`build` all pass
- Manually verified live (not part of the automated suite): Nominatim search, OSRM route/table
  calls, Overpass nearby-POI query (one transient 503 observed and self-recovered on retry);
  confirmed `GET /experiences` with lat/lng/radius still returns 200 with real DB results when
  `LOCATION_SERVICES_ENABLED=false`, while `/location/search` degrades to `{"items": []}`

### Explicitly not implemented (deferred by design)

- Gemini/conversational AI, semantic embeddings/pgvector, ML ranking, traveler affinity,
  deterministic feasibility engine, AI composer/itinerary, dynamic replanning, weather/events,
  provider analytics, booking/payments, emergency backend, real-time GPS turn-by-turn navigation
  — all remain scoped to their respective later phases per docs/ROADMAP.md

---

## [Phase 3] 2026-09-22 — Authentication, Roles & Provider Foundation

### Added — Authentication (`apps/api/`)

- `src/core/security.py` — Argon2 password hashing (`pwdlib`), HS256 JWT issuance/verification
  with **distinct** access/refresh secrets, `TokenError` for uniform 401 handling
- `src/core/cookies.py` — HttpOnly refresh cookie helpers (`__Host-`-prefixed when Secure;
  Path=/ required by that prefix)
- `src/core/deps.py` — centralized `get_current_user`, `require_role`, `require_traveler/
  _provider_role/_admin`, `get_current_provider`; a stale `role` JWT claim is never trusted —
  the User row is re-loaded from the database on every request
- `src/models/auth_session.py` — `AuthSession` (hashed refresh tokens only, rotation via
  `replaced_by_session_id`, revocation, reuse detection)
- `src/services/auth.py` — register/login/refresh-rotation/logout orchestration
- `src/schemas/auth.py`, `src/schemas/provider.py`, `src/schemas/experience_write.py`,
  `src/schemas/availability.py`, `src/schemas/category.py`
- Endpoints: `POST /api/v1/auth/{register,login,refresh,logout}`, `GET /api/v1/auth/me`,
  `GET /api/v1/categories`
- `scripts/create_admin.py` — the only way to create an ADMIN account; reads
  `ADMIN_SEED_EMAIL`/`ADMIN_SEED_PASSWORD` from the environment, never hardcoded
- Alembic migration `auth_sessions and experience_availability` — verified from a fresh
  database and confirmed to preserve all 353 Phase 2 experiences / 311 providers when applied
  to the existing seeded database

### Added — Provider & Experience CRUD

- `GET/PUT /api/v1/providers/me`, `GET /api/v1/providers/me/experiences`
- `POST /api/v1/experiences`, `PATCH /api/v1/experiences/{id}`,
  `DELETE /api/v1/experiences/{id}` (soft-delete → `status="inactive"`) — `provider_id` is
  never accepted from the request body, always derived from the authenticated provider
- `src/models/availability.py` — `ExperienceAvailability` (distinct from the Phase 2 recurring
  `ExperienceOpeningHour`) + `GET/POST/PATCH/DELETE /api/v1/experiences/{id}/availability[/{id}]`
  (owner-scoped mutations, public read)
- Explicit provider lineages: catalog-imported (`source_type="overture_places"`) and synthetic
  demo (`source_type="synthetic"`) providers have no `user_id` and cannot log in; only
  `source_type="registered"` providers (created via `/auth/register`) are real accounts —
  provider claiming is deliberately deferred to a later phase

### Fixed

- **Phase 2's `scripts/seed.py` would have destroyed real account data on reseed.** The
  original `reset_tables()` unconditionally deleted *all* `Provider`/`Location`/`Experience`
  rows and recreated `ExperienceCategory` with fresh UUIDs on every run — harmless while only
  Overture/synthetic data existed, but Phase 3 registered providers/experiences reference
  those same tables. Fixed to scope every delete to
  `source_type IN ("overture_places", "synthetic")` and to upsert categories by slug (stable
  IDs) instead of recreating them. Verified: a registered provider, its experience, and its
  availability slot all survive a full reseed.
- `src/core/errors.py`'s `RequestValidationError` handler crashed with a secondary
  `TypeError: Object of type ValueError is not JSON serializable` whenever a Pydantic
  `model_validator` raised a plain `ValueError` (e.g. "maximum_group_size must be >=
  minimum_group_size") — FastAPI/Pydantic v2 puts the raised exception object itself in
  `ctx.error`, which isn't JSON-serializable. Found via the new test suite; fixed by stripping
  `ctx` before encoding, so these cases now correctly return 422 instead of a bare 500.

### Added — Frontend

- `lib/auth/tokenStore.ts` — in-memory-only access token (module singleton, never React state,
  never localStorage/sessionStorage/IndexedDB)
- `lib/auth/AuthContext.tsx` — `AuthProvider`/`useAuth`; bootstraps via `/auth/refresh` on load
  so a page reload can silently restore a session from the HttpOnly cookie
- `lib/api/client.ts` — every request sends `credentials: "include"` and a `Bearer` header when
  a token is held; a 401 on any non-auth endpoint triggers exactly one shared refresh-and-retry
  (never an unbounded loop; login/register/refresh themselves are excluded)
- `lib/api/auth.ts`, `lib/api/providers.ts`, `lib/api/experiencesWrite.ts`, `lib/api/categories.ts`
- Real `/login` and `/register` forms (role choice, validation, loading/error states,
  role-aware post-auth redirect) replacing the Phase 1 UI placeholders
- Role-aware `SiteHeader` (identity + logout when signed in; nav filtered by role)
- `apps/web/proxy.ts` — Next.js 16 Proxy file convention; optimistic, presence-only refresh-
  cookie check for `/trip`, `/saved`, `/provider*` (redirects to `/login`); explicitly documented
  as *not* the authorization boundary — FastAPI re-checks everything independently
- `components/common/RequireRole.tsx` — client-side render guard (UX only, same caveat as proxy)
- Provider dashboard (`app/provider/`) now shows real profile + experience counts; no fabricated
  views/bookings/conversion numbers — shows "Analytics will appear once traveler interactions
  are enabled" instead
- `/provider/experiences` is now a full CRUD UI: `components/provider/ExperienceForm.tsx`
  (create/edit, structured per-day opening hours), `components/provider/AvailabilityManager.tsx`
  (add/deactivate bookable time slots), `/provider/experiences/new`,
  `/provider/experiences/[id]` — Phase 1 visual design preserved throughout
- `types/auth.ts`, `types/provider-api.ts` — typed request/response shapes mirroring the backend
  schemas

### Added — Tests

- 45 new backend tests (72 total): registration (traveler/provider/ADMIN-rejected/duplicate-
  email/email-normalization), login (success/wrong-password/generic-error), `/auth/me`, logout,
  refresh rotation + old-token rejection + reuse-triggers-mass-revocation, role authorization,
  provider profile retrieval/update/protected-field-rejection, experience create/update/
  deactivate, ownership isolation (provider A cannot touch provider B's experience or
  availability — 404, not 403, to avoid disclosing existence), catalog-experience protection,
  input validation (group size range, negative price), CORS wildcard/credentials check, refresh
  cookie HttpOnly/SameSite/Path flags, seed-safety (registered data survives reseed)

### Verified

- `pytest` (72/72), `ruff check`, `mypy src --strict` (apps/api) — all pass
- `npm run lint`, `npx tsc --noEmit`, `npm run build` (apps/web) — all pass
- Manual end-to-end verification: traveler register → login → `/auth/me` → logout → refresh
  correctly rejected; provider register → create experience → update → add availability →
  deactivate; Provider A blocked (404) from mutating Provider B's experience/availability;
  traveler blocked (403) from the provider-create endpoint; ADMIN self-registration rejected
  (422); catalog-imported (Overture) experience protected from provider mutation (404); `proxy.ts`
  redirect confirmed with and without a real refresh cookie (same-hostname requirement noted)

### Explicitly Not Implemented (by design — later phases)

- Provider claiming, password reset, email verification, social login, MFA, full admin
  dashboard, Gemini/AI, semantic search, ML ranking, real map integration, booking/payments,
  dynamic replanning, provider analytics backend, safety backend integrations

### Known limitation

- `apps/web/proxy.ts` checks only for refresh-cookie *presence*, not validity — by design (no
  JWT secret lives in the edge/proxy runtime). A browser must use a consistent hostname
  (`localhost` vs `127.0.0.1`) between the frontend and any manually-tested API calls for the
  cookie to be recognized; this does not affect normal same-origin browser usage.

### Current State

- **Phase**: 3 — Authentication, Roles & Provider Foundation ✅
- **Next phase**: Phase 4 — Experience Discovery, Catalog & OSM Location Layer

---

## [Phase 2] 2026-09-22 — Database, Models, Open Data Ingestion & Realistic Experience Data

### Added — Database (`apps/api/`)

- Async SQLAlchemy 2.0 engine/session factory (`src/core/db.py`), SQLite dev / PostgreSQL+asyncpg
  compatible — no SQLite-only syntax anywhere in `src/models`
- Alembic configured for async migrations (`alembic/`); initial migration generated and verified
  against a fresh database
- Models: `User`, `Traveler`, `Provider`, `ExperienceCategory`, `Location`, `Experience`,
  `ExperienceOpeningHour`, plus shared `UUIDPrimaryKeyMixin`, `TimestampMixin`, `ProvenanceMixin`
- Unique constraint on `Experience(source_type, source_record_id)` to prevent duplicate ingestion

### Added — Open data ingestion

- `scripts/ingest_overture.py` — queries **Overture Maps Places** (release `2026-08-19.0`)
  directly from its public cloud Parquet store via DuckDB `spatial`/`httpfs` (no API key, no
  full-dataset download — bbox pushed down to Parquet row-group statistics) for a Mumbai
  bounding box spanning Colaba/Fort/Churchgate/Marine Drive/Dadar/Matunga/Bandra/Juhu/
  Andheri/Lower Parel/Powai
- `src/core/category_map.py` — single source of truth for the 20-slug LocaLens category
  taxonomy and its mapping from Overture's `categories.primary` values
- Deterministic normalization, deduplication (source ID + normalized-name/proximity), and
  validation (coordinates, name, mapped category, not permanently closed)
- Provenance preserved per record: source dataset/provider, record ID, license
  (predominantly `CDLA-Permissive-2.0`), confidence, release version, access timestamp
- `scripts/synthetic_data.py` — deterministic, templated synthetic provider/experience
  generator (fictional names, controlled templates, clearly labelled `is_synthetic=true`)
- `scripts/seed.py` — full reseed script; last run: **353 experiences** (288 Overture-derived +
  65 synthetic), **311 providers** (261 catalog-imported + 50 synthetic), **20 categories**,
  **353 locations**, **0 duplicate source IDs**
- `data/README.md` — full source, licensing, attribution, and provenance documentation
- `data/processed/overture_experiences.json` + `ingestion_report.json` committed (small,
  reproducible snapshot); raw Overture export gitignored (`data/raw/`)

### Added — API

- `src/repositories/` — `ExperienceRepository`, `ProviderRepository`, `CategoryRepository`,
  `LocationRepository`; route handlers stay thin
- `src/schemas/experience.py` — Pydantic response schemas (summary + detail); no SQLAlchemy
  model is ever returned directly
- `GET /api/v1/experiences` (category/city/status/limit/offset filters, paginated) and
  `GET /api/v1/experiences/{id}` (200/404)

### Added — Frontend integration

- `lib/api/experiences.ts`, `lib/api/experienceAdapter.ts`, `types/api.ts` — typed fetch +
  adapter mapping API responses onto the existing Phase 1 `Experience` UI type (distance
  computed from a fixed Mumbai reference point; nullable rating/hours/accessibility rendered
  honestly instead of fabricated)
- Discover page and experience detail page now render live database records, with loading
  skeletons and an `ErrorState` + retry on fetch failure — Phase 1 visual design unchanged
- `types/experience.ts` widened (nullable rating/duration/accessibility, `categoryLabel`,
  `isPriceEstimated`) to represent real data honestly; mock data retained for isolated UI
  testing and the landing page's illustrative cards (still clearly labelled)

### Added — Tests

- 27 backend tests: database/session/relationship tests (in-memory SQLite + `StaticPool`),
  ingestion pure-function unit tests (normalization, dedup, validation, provenance), synthetic
  data determinism tests, API list/detail/pagination/category-filter/404 tests

### Verified

- `pytest`, `ruff check`, `mypy src --strict` (apps/api) — all pass
- `npm run lint`, `npx tsc --noEmit`, `npm run build` (apps/web) — all pass
- Live end-to-end check: API served from seeded SQLite DB, frontend production build fetched
  and rendered both a real Overture-derived and a synthetic experience correctly, including
  correct demo/source badging

### Explicitly Not Implemented (by design — later phases)

- Authentication, JWT, database-backed sessions, Gemini AI/Live, semantic search/embeddings,
  ML ranking, real map integration (MapLibre/Nominatim/OSRM/Overpass), weather/events, booking,
  dynamic replanning, provider analytics backend

### Known limitation

- Next.js streaming (via `loading.tsx` Suspense boundaries) means a request for a
  non-existent experience ID returns HTTP 200 for the initial shell before the client renders
  the not-found state, rather than a raw 404 status — a framework-level trade-off, not a
  routing defect (the correct not-found UI does render).

### Current State

- **Phase**: 2 — Database, Models, Open Data Ingestion & Realistic Experience Data ✅
- **Next phase**: Phase 3 — Authentication, Roles & Provider Foundation

---

## [Phase 1] 2026-09-22 — Application Foundation & UI System

### Added — Frontend (`apps/web/`)

- Next.js 16 (App Router) + React 19 + TypeScript strict + Tailwind CSS v4 scaffold
- Centralized design token system (light + dark) in `app/globals.css` — no hardcoded colors
  in components
- Reusable UI primitives: `Button`, `Badge`, `Card`, `Input`/`Textarea`, `Skeleton`,
  `EmptyState`, `ErrorState`, `IconButton`, `DemoDataBadge`, `SectionHeading`
- Global app shell: `SiteHeader` (responsive nav + mobile menu), `SiteFooter`, `MobileTabBar`,
  skip-to-content link
- Domain components: `ConversationalDiscoveryInput` (text + disabled voice affordance),
  `CategoryChips`, `FilterBar`, `ExperienceCard` (compact/standard/featured variants),
  `ExperienceDetail`, `ExperienceComposer` (AI composer presentation shell — no fake reasoning),
  `ItineraryTimeline`/`ItineraryItemCard`/`ReplanBanner`, `ProviderExperienceRow`,
  `InsightStatCard`/`InsightPlaceholderChart`, `EmergencyButton`/`SafetyResourceCard`,
  `MapSurface` (MapLibre placeholder)
- Routes: `/`, `/discover`, `/discover/[id]`, `/login`, `/register`, `/trip`, `/trip/[id]`,
  `/saved`, `/safety`, `/safety/emergency`, `/provider`, `/provider/experiences`,
  `/provider/insights`, plus root `loading.tsx`, `error.tsx`, `not-found.tsx`, and route-level
  `loading.tsx` for discover/trip/provider
- Typed API client (`lib/api/client.ts`) with normalized error handling; `getHealth()` is the
  only live backend call in this phase
- Mock/demo data in `mocks/` — every record carries `isSynthetic: true`
- Accessibility baseline: semantic HTML, visible focus states, ARIA labels/roles, skip link,
  `aria-live` status regions, reduced-motion support

### Added — Backend (`apps/api/`)

- FastAPI application factory with CORS, structured error handlers, and startup credential
  validation (warns on missing optional adapter keys, fails on missing required production config)
- `GET /api/v1/health` endpoint
- Pydantic v2 / pydantic-settings environment configuration
- Adapter Protocol interfaces + mock implementations: `AIAdapter`, `GeocodingAdapter`,
  `RoutingAdapter`, `POIAdapter`, `WeatherAdapter`, `EventAdapter`, `MapTilesAdapter`
- pytest smoke test for the health endpoint; ruff + mypy --strict configuration

### Added — Developer Experience

- `scripts/dev.ps1` and `scripts/dev.sh` to run both dev servers together

### Verified

- `npm run lint`, `npx tsc --noEmit`, `npm run build` (apps/web) — all pass
- `pytest`, `ruff check`, `mypy src` (apps/api) — all pass
- Production build serves all routes with HTTP 200; `/api/v1/health` reachable with correct
  CORS headers for `http://localhost:3000`

### Explicitly Not Implemented (by design — later phases)

- Gemini AI, Gemini Live voice, database, authentication backend, semantic search, ML ranking,
  real map integration (MapLibre), booking, dynamic replanning engine, provider intelligence
  backend, real emergency integrations

### Current State

- **Phase**: 1 — Application Foundation & UI System ✅
- **Next phase**: Phase 2 — Database, Models & Realistic Seed Data

---

## [Phase 0] 2026-09-22 — Foundation Established

### Added

- Repository initialized (`git init`)
- `.gitignore` — covers Python, Node.js, Next.js, SQLite, secrets, IDEs, and OS artifacts
- `.env.example` — full environment variable contract with comments; no real secrets
- `README.md` — project overview for human engineers and AI coding agents
- `docs/AI_CONTEXT.md` — primary orientation document for AI coding agents; includes invariants, stack, module ownership, and safe modification guidelines
- `docs/ARCHITECTURE.md` — full logical architecture document; all 10 capability modules, data flows, adapter contracts, database boundary, AI boundary, voice architecture, and safety isolation
- `docs/PRODUCT_CONTRACT.md` — product purpose, target users, traveler and provider experience, differentiators, capability status table, non-goals, demo strategy
- `docs/PROJECT_STATE.md` — current implementation status tracker; all phases; known risks; next milestone
- `docs/DECISIONS.md` — 16 architectural decision records (ADR-001 through ADR-016)
- `docs/TASKS.md` — phase-based high-signal task backlog for all 13 phases
- `docs/ROADMAP.md` — 13-phase roadmap with dependency graph, deliverables, and phase gates
- `docs/CHANGELOG.md` — this file
- `apps/web/` — directory placeholder for Next.js frontend (Phase 1)
- `apps/api/` — directory placeholder for FastAPI backend (Phase 1)
- `scripts/` — directory placeholder for developer utility scripts
- `tests/` — directory placeholder for cross-app integration tests

### Architectural Contract Established

- 13 non-negotiable architectural rules documented in `ARCHITECTURE.md`
- 16 architectural decision records documented in `DECISIONS.md`
- Critical invariants documented in `AI_CONTEXT.md`
- Phase 0 milestone: documentation-first, no application code

### Current State

- **Phase**: 0 — Reset, Baseline & Master Contract ✅
- **Next phase**: Phase 1 — Application Foundation & UI System
- **Application code**: None (by design)
- **Database**: None (by design)
- **External integrations**: None (by design)
