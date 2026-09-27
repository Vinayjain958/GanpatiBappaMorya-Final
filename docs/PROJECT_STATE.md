# LocaLens — Project State

> This file tracks the current implementation state of every major capability.
> Update this file whenever a phase milestone is reached.
> Last updated: 2026-09-25 (Phase 0-9 Reconciliation)

---

## Current Phase

**PHASE 9 — Real-Time Context + Events + Dynamic Replanning — Complete**

Phases 0-9 are implemented and verified as of this reconciliation pass (see
`docs/DECISIONS.md` ADR-055 and `docs/CHANGELOG.md`'s 2026-09-25 reconciliation entry for the
real bugs found and fixed during verification). Phase 10 has not started.

### Additive geospatial visualization (2026-09-27)

- The existing `MapSurface` now accepts optional clustered map annotations, itinerary route geometries, and explicit focus/fit requests; discovery continues to use its existing experience layer and behavior.
- Saved itinerary details show verified itinerary stops, sequence, selected/affected/locked state, selection synchronization with the text timeline, fit controls, and explicit nearby exploration.
- Route geometry is requested only after the traveler enables it, uses the existing `/api/v1/location/route` API sequentially, and only draws OSRM geometry. Selected-stop weather uses the existing context API and status labels.
- No new backend endpoint, map/weather tile adapter, or database migration was added. Weather tiles remain disabled because no configured tile capability is present. No device location tracking was added.
- Verification: frontend Vitest 98/98, TypeScript and changed-file ESLint pass; Webpack production build passes (the default Turbopack builder could not bind a sandbox port). Backend pytest 450 passes. Whole-repository lint/type checks still report existing findings in untouched files; manual credentialed trip smoke testing requires an API/database environment not included in this archive (details in `docs/CHANGELOG.md`).

---

## Phase Completion Status

| Phase | Name | Status |
|---|---|---|
| 0 | Reset, Baseline & Master Contract | ✅ Complete |
| 1 | Application Foundation & UI System | ✅ Complete |
| 2 | Database, Models, Open Data Ingestion & Realistic Experience Data | ✅ Complete |
| 3 | Authentication, Roles & Provider Foundation | ✅ Complete |
| 4 | Experience Discovery, Catalog & OSM Location Layer | ✅ Complete |
| 5 | Conversational AI + Gemini Live Voice Agent | ✅ Complete (Gemini text LIVE VERIFIED; Live voice WebSocket path NOT VERIFIED — requires a browser mic session, not exercisable headlessly) |
| 6 | Semantic Retrieval + Constraint / Feasibility Engine | ✅ Complete (SQLite semantic retrieval + feasibility LIVE VERIFIED; PostgreSQL/pgvector path NOT VERIFIED — no Postgres instance available) |
| 7 | Real ML Ranking + Feedback Learning | ✅ Complete (ranking budget-filter bug found and fixed this reconciliation — see ADR-055) |
| 8 | Deterministic Itinerary Composition with Gemini Narrative Generation | ✅ Complete (Gemini narrative generation LIVE VERIFIED this session; PostgreSQL migration path NOT VERIFIED) |
| 9 | Real-Time Context + Events + Dynamic Replanning | ✅ Complete (OpenWeather + Ticketmaster LIVE VERIFIED this reconciliation with real API keys; replanning crash bugs found and fixed — see ADR-055) |
| 10 | Provider Intelligence & Two-Sided Marketplace | ✅ Complete |
| 11 | Safety & Emergency | ✅ Complete |
| 12 | Full Integration, Testing, Hardening & Deployment | ❌ Blocked (missing deployment credentials, postgres, docker) |

---

## Implemented

- Repository initialized with `git init`
- `.gitignore` (Python, Node, Next.js, SQLite, secrets, IDEs)
- `.env.example` (full environment variable contract)
- `README.md` (project overview for humans and AI agents)
- `docs/AI_CONTEXT.md` (AI agent orientation and invariants)
- `docs/ARCHITECTURE.md` (full logical architecture)
- `docs/PRODUCT_CONTRACT.md` (product purpose, users, capabilities)
- `docs/PROJECT_STATE.md` (this file)
- `docs/DECISIONS.md` (16 architectural decisions recorded)
- `docs/TASKS.md` (phase-based task backlog)
- `docs/ROADMAP.md` (13-phase roadmap with dependencies)
- `docs/CHANGELOG.md` (initial changelog entry)
- `apps/web/` directory placeholder (Next.js — Phase 1)
- `apps/api/` directory placeholder (FastAPI — Phase 1)
- `scripts/` directory placeholder
- `tests/` directory placeholder

---

- **`apps/web/`** — Next.js 16 (App Router, React 19, TypeScript strict, Tailwind CSS v4)
  - Centralized design tokens (light/dark) in `app/globals.css`
  - Reusable UI library: `components/ui/` (Button, Badge, Card, Input, Skeleton, EmptyState,
    ErrorState, IconButton, DemoDataBadge, SectionHeading)
  - Layout: `components/layout/` (AppShell, SiteHeader, SiteFooter, PageContainer),
    `components/navigation/` (NavLink, MobileTabBar)
  - Domain components: `components/discovery/` (ConversationalDiscoveryInput, CategoryChips,
    FilterBar), `components/experience/` (ExperienceCard w/ 3 variants, ExperienceDetail,
    ExperienceComposer), `components/trip/` (ItineraryTimeline, ItineraryItemCard, ReplanBanner),
    `components/provider/` (ProviderExperienceRow, InsightStatCard, InsightPlaceholderChart),
    `components/safety/` (EmergencyButton, SafetyResourceCard), `components/common/`
    (MapSurface placeholder, AuthCard, ApiStatusBadge)
  - Routes: `/`, `/discover`, `/discover/[id]`, `/login`, `/register`, `/trip`, `/trip/[id]`,
    `/saved`, `/safety`, `/safety/emergency`, `/provider`, `/provider/experiences`,
    `/provider/insights`, plus root `loading.tsx` / `error.tsx` / `not-found.tsx`
  - `lib/api/client.ts` — typed fetch wrapper; only `getHealth()` is wired to a real endpoint
  - `lib/config/env.ts`, `lib/constants/`, `lib/utils/cn.ts`
  - `types/` (Experience, Trip, Provider) and `mocks/` (labelled `isSynthetic: true`)
  - `hooks/useMediaQuery`, `hooks/useHealthCheck`
  - Verified: `npm run lint`, `npx tsc --noEmit`, `npm run build` all pass; all routes return
    HTTP 200 against a production build
- **`apps/api/`** — FastAPI backend
  - `src/core/` — Pydantic settings (`config.py`), app factory (`app.py`), structured error
    handlers (`errors.py`), logging (`logging.py`), startup credential validation (`startup.py`)
  - `src/api/v1/health.py` — `GET /api/v1/health` → `{status, service, version}`
  - CORS configured for `http://localhost:3000`
  - `src/adapters/` — Python Protocol interfaces + mock implementations for AI, Geocoding,
    Routing, POI, Weather, Events, MapTiles (all raise `NotImplementedError` until their phase)
  - Verified: `pytest`, `ruff check`, `mypy --strict` all pass; server runs and serves
    `/api/v1/health` with correct CORS headers
- `scripts/dev.ps1`, `scripts/dev.sh` — run both dev servers together

### Phase 2 — Database, Models, Open Data Ingestion & Realistic Experience Data

- `apps/api/src/core/db.py` — async SQLAlchemy engine/session factory (SQLite dev,
  PostgreSQL/asyncpg-compatible; no SQLite-only syntax)
- `apps/api/alembic/` — configured for async migrations; one migration (`initial schema`)
  verified against a fresh database
- `apps/api/src/models/` — `User`, `Traveler`, `Provider`, `ExperienceCategory`, `Location`,
  `Experience`, `ExperienceOpeningHour`, plus `ProvenanceMixin` / `TimestampMixin` /
  `UUIDPrimaryKeyMixin`
- `apps/api/src/core/category_map.py` — the 20-category LocaLens taxonomy and its mapping
  from Overture `categories.primary` values (single source of truth)
- `apps/api/scripts/ingest_overture.py` — queries Overture Maps Places (release `2026-08-19.0`)
  for a Mumbai bounding box via DuckDB spatial/httpfs, normalizes, deduplicates, validates,
  and writes `data/processed/overture_experiences.json` + an ingestion report
- `apps/api/scripts/synthetic_data.py` — deterministic, templated synthetic provider/experience
  generator (fictional, clearly labelled `is_synthetic=true`)
- `apps/api/scripts/seed.py` — full reseed script; last run produced 353 experiences (288
  Overture-derived + 65 synthetic), 311 providers, 20 categories, 353 locations, 0 duplicate
  source IDs — see `data/README.md` for the full breakdown
- `apps/api/src/repositories/` — `ExperienceRepository`, `ProviderRepository`,
  `CategoryRepository`, `LocationRepository` (thin route handlers, queries live here)
- `apps/api/src/schemas/experience.py` — Pydantic response schemas (summary + detail); no
  SQLAlchemy model is ever returned directly from a route
- `GET /api/v1/experiences` (category/city/status/limit/offset filters) and
  `GET /api/v1/experiences/{id}` (200/404) — verified against the seeded database
- `apps/web/lib/api/experiences.ts`, `experienceAdapter.ts`, `types/api.ts` — typed fetch +
  adapter mapping API responses onto the existing Phase 1 `Experience` UI type
- `apps/web/app/discover/` — Discover grid and detail page now render live database records
  (loading skeletons + `ErrorState` with retry on fetch failure; mock data kept only for the
  landing page's illustrative cards, clearly labelled `DemoDataBadge`)
- 27 backend tests (database/session/relationships, ingestion pure-function unit tests,
  synthetic-data determinism, API list/detail/pagination/filter/404) — all passing alongside
  `ruff`, `mypy --strict` (relaxed for `scripts/` — see `pyproject.toml`), and frontend
  `lint`/`tsc --noEmit`/`build`

### Phase 3 — Authentication, Roles & Provider Foundation

- `apps/api/src/core/security.py` — Argon2 password hashing (`pwdlib`), HS256 JWT issuance/
  verification with distinct access/refresh secrets, `TokenError` never leaks parsing detail
- `apps/api/src/core/cookies.py` — HttpOnly refresh cookie helpers (`__Host-` prefix when Secure)
- `apps/api/src/models/auth_session.py` — `AuthSession` (hashed refresh tokens, rotation,
  revocation, reuse-detection); `apps/api/src/models/availability.py` — `ExperienceAvailability`
- Alembic migration `auth sessions and experience availability` — verified from a fresh database
  and confirmed to preserve all 353 Phase 2 experiences / 311 providers on top of an existing DB
- `apps/api/src/core/deps.py` — `get_current_user`, `require_role`, `require_traveler/_provider/
  _admin`, `get_current_provider` (centralized; re-loads the User from the DB every request —
  a stale role claim in the JWT is never trusted alone)
- `apps/api/src/services/auth.py` — register/login/refresh-rotation/logout orchestration
- Endpoints: `POST /api/v1/auth/{register,login,refresh,logout}`, `GET /api/v1/auth/me`,
  `GET /api/v1/categories`, `GET/PUT /api/v1/providers/me`, `GET /api/v1/providers/me/experiences`,
  `POST /api/v1/experiences`, `PATCH/DELETE /api/v1/experiences/{id}`,
  `GET/POST/PATCH/DELETE /api/v1/experiences/{id}/availability[/{availability_id}]`
- `apps/api/scripts/create_admin.py` — the only way to create an ADMIN account; reads
  `ADMIN_SEED_EMAIL`/`ADMIN_SEED_PASSWORD` from the environment, never hardcoded
- **Bug found and fixed**: Phase 2's `scripts/seed.py` originally wiped and recreated *all*
  providers and categories (with fresh UUIDs) on every reseed — this would have deleted
  real registered accounts' data and orphaned their `category_id` foreign keys. Fixed to scope
  deletes to `source_type in ("overture_places", "synthetic")` and upsert categories by slug.
- Frontend: `lib/auth/tokenStore.ts` (in-memory access token), `lib/auth/AuthContext.tsx`
  (`AuthProvider`/`useAuth`, bootstrap-refresh on load), `lib/api/client.ts` (Bearer header +
  `credentials: "include"` + single shared 401-refresh-and-retry), real `/login` and `/register`
  forms, role-aware `SiteHeader`, `apps/web/proxy.ts` (optimistic cookie-presence route guard for
  `/trip`, `/saved`, `/provider*`), provider dashboard + `/provider/experiences` full CRUD UI
  (`ExperienceForm`, `AvailabilityManager`) backed by the real API — Phase 1 visual design intact
- 72 backend tests total (45 new: registration/login/refresh-rotation/reuse-detection/logout,
  role authorization, provider ownership isolation, catalog-experience protection, availability
  ownership, CORS/cookie flag checks, seed-safety) — all passing alongside `ruff`,
  `mypy --strict`, and frontend `lint`/`tsc --noEmit`/`build`

### Phase 4 — Experience Discovery, Catalog & OSM Location Layer

- `apps/api/src/core/{http_client,cache,rate_limit,geo}.py` — shared async httpx client
  singleton, generic `TTLCache[T]`, `IntervalRateLimiter`, portable Haversine/bounding-box math
  (`EARTH_RADIUS_KM`, `validate_coordinates`) — no PostGIS/SQLite spatial extension used
- `apps/api/src/adapters/{geocoding,routing,poi,errors}.py` — real `NominatimGeocodingAdapter`,
  `OSRMRoutingAdapter` (route + travel-time matrix), `OverpassPOIAdapter` (deterministic QL from
  a category allowlist); typed `AdapterTimeoutError`/`AdapterRateLimitedError`/
  `AdapterUnavailableError`/`AdapterNoResultError`; each rate-limited + TTL-cached per its own
  settings (see `.env.example` "Maps & Location" section)
- `apps/api/src/core/location.py` — DI providers switching to `Mock*Adapter` when
  `LOCATION_SERVICES_ENABLED=false`, so the catalog never breaks if external services are down
- `apps/api/src/api/v1/location.py` — `GET /api/v1/location/{search,reverse,nearby-pois}`,
  `POST /api/v1/location/{route,travel-time-matrix}`
- `apps/api/src/repositories/experience_repository.py` — `ExperienceFilters` (keyword + bbox),
  `search()` does a bounded candidate fetch; sorting/pagination stays in Python, never pushed to
  SQL, to keep radius search portable across SQLite/PostgreSQL
- `apps/api/src/services/discovery.py` — `ExperienceDiscoveryService`, deterministic
  non-personalized relevance scoring (documented field weights) — explicitly not ML/AI
- `GET /api/v1/experiences` extended with keyword/category/price/duration/lat+lng+radius_km/sort
  filters, plus per-result `distance_km`/`travel_time_minutes`/`travel_time_source` enrichment
  (capped at `OSRM_MAX_MATRIX_DESTINATIONS`, gracefully skipped if adapters are unavailable)
- `apps/api/src/api/v1/categories.py` — `GET /api/v1/categories` (used by the provider
  experience-location picker)
- 142 backend tests total (70 new: geo math, discovery service/API, adapter unit tests against
  fake HTTP clients — no real network calls in the suite, location API, categories) — all passing
  alongside `ruff`, `mypy --strict`
- Frontend: `lib/config/map.ts`, `lib/geo/{haversine,geojson}.ts`, `lib/api/location.ts`,
  `types/{location,discovery}.ts`, `lib/discovery/urlState.ts`,
  `hooks/{useExperienceDiscovery,useUserLocation,useLocationSearch}.ts` (all explicit-trigger —
  geolocation and place search are never auto-requested)
- `components/common/MapSurface.tsx` — real MapLibre GL JS (replacing the Phase 1 placeholder),
  clustered GeoJSON experience source, origin/route sources, "Search this area" bounds-triggered
  re-query (never auto-queries on pan/zoom alone), graceful fallback UI if map init fails
- `app/discover/DiscoverExperience.tsx` — URL-synced discovery state
  (`?q=&category=&lat=&lng=&radius_km=&sort=`), `LocationBar`, mobile list/map toggle, real map
- `components/experience/ExperienceDetail.tsx` — "Set a starting point" + "Show route" using the
  real routing adapter, labels estimated vs. OSRM-sourced travel time
- `components/provider/ExperienceForm.tsx` — location-search picker (explicit pick only, never
  silently overwrites existing form values)
- Verified live (not just mocked in tests): Nominatim search, OSRM route + table calls, Overpass
  nearby-POI query (observed one transient 503 that self-recovered on retry — confirms graceful
  degradation works as designed); confirmed catalog discovery still returns 200 with real DB
  results when `LOCATION_SERVICES_ENABLED=false`, while `/location/search` degrades to `{"items": []}`
- All frontend checks passing: `npx tsc --noEmit`, `npm run lint`, `npm run build` (15 routes)

### Phase 5 — Conversational AI + Gemini Live Voice Agent

- `apps/api/src/adapters/ai.py` — real `GeminiAIAdapter` (google-genai SDK, `gemini-3.8-flash`
  text / `gemini-3.8-live` Live as originally configured at Phase 5; the text model was later
  switched to `gemini-2.5-flash` — see the 2026-09-25 live debugging session below — the current
  working default is `GEMINI_MODEL_TEXT=gemini-2.5-flash` / `GEMINI_MODEL_LIVE=gemini-3.8-live`),
  `MockAIAdapter` rewritten to a graceful deterministic
  keyword extraction for `generate_text` (never raises — text mode stays usable without Gemini)
  while `issue_live_token` still fails loudly (voice is never faked); `src/core/ai.py` DI
  provider mirrors the Phase 4 `location.py` pattern, gated on `GEMINI_ENABLED` + key presence
- `apps/api/src/schemas/conversation.py` — `TravelerContext` (shared by text and voice),
  `SearchExperiencesArgs`/`Result`, conversation turn/detail/create schemas, `LiveTokenResponse`
- `apps/api/src/services/ai_tools.py` — `SEARCH_EXPERIENCES_DECLARATION` (single source of
  truth for the tool schema) + `execute_search_experiences()`, a thin wrapper around the
  existing Phase 4 `ExperienceDiscoveryService` — zero new search logic
- `apps/api/src/services/conversation.py` — text-turn orchestration: one Gemini call per turn
  (structured `TravelerContext` extraction only), bounded recent-history window
  (`CONVERSATION_HISTORY_WINDOW`), deterministic template assistant reply (never a second
  free-form Gemini call, so text-mode prose can never fabricate result claims)
- `apps/api/src/models/conversation_session.py`, `conversation_message.py` — user-owned,
  cascade-deleted; `latest_traveler_context` JSON snapshot column; transcript text only, audio
  is never persisted anywhere. New Alembic migration verified against both a fresh DB and the
  existing seeded DB (353 experiences / 311 providers unaffected)
- `apps/api/src/api/v1/conversation.py` — `POST /conversations`, `POST /conversations/{id}/
  messages`, `GET /conversations/{id}`, `POST /conversations/{id}/tool-calls` (the voice-path
  bridge: the browser forwards Gemini Live's tool_call here verbatim; this endpoint is the only
  place `search_experiences` actually executes — never the browser). Ownership 404s (never
  403s) for another user's conversation, matching the existing non-disclosure pattern
- `apps/api/src/api/v1/auth.py` — `POST /auth/live-token`, `require_traveler`-gated, returns an
  ephemeral Gemini Live token whose `live_connect_constraints` locks the model/tools/system
  instruction server-side — a tampered client cannot redefine them. `GEMINI_API_KEY` never
  leaves the backend; the token itself is never logged or persisted
- Frontend: `lib/voice/{audioCapture,audioPlayback,pcmResample,geminiLiveClient}.ts` (real
  AudioWorklet-based 16-bit/16kHz PCM mic capture, 24kHz scheduled PCM playback with barge-in
  support, the Gemini Live session wrapper handling transcription/tool-calls/session
  resumption/GoAway), `public/worklets/pcm-capture-worklet.js`, `hooks/{useVoiceAgent,
  useTextConversation}.ts`, `components/voice/{VoiceOrb,VoiceTranscriptPanel,
  VoiceControlButton}.tsx`
- `components/discovery/ConversationalDiscoveryInput.tsx` upgraded in place — the Phase 1
  permanently-disabled mic button now drives a real Gemini Live session; text submit now also
  runs a real conversational turn. `app/discover/DiscoverExperience.tsx` threads a
  `Partial<DiscoveryState>` patch callback through — `setDiscoveryState` itself stays private,
  matching the existing `onSubmitQuery`/`onChange` pattern
- `lib/discovery/travelerContextToPatch.ts` — the app-controlled, deterministic translation
  from AI-extracted intent to `DiscoveryState` (never the model); `location_text` is
  deliberately never mapped to `lat`/`lng` (preserves the Phase 4 explicit-geocoding-only policy)
- 30 new backend tests (172 total) — AI adapter (mock + real against a fake `google-genai` SDK
  client, never real network), conversation service/API (ownership isolation, tool-call
  validation, unknown-tool rejection), live-token endpoint (role gate, mock-adapter-always-503,
  real-shape success) — all passing alongside `ruff`, `mypy --strict`
- Vitest newly introduced for the frontend (no prior test framework existed), scoped narrowly
  to pure high-risk logic: 20 tests covering the discovery-patch translator and the PCM
  encode/decode/resample math — all passing alongside `tsc --noEmit`, `eslint`, `next build`
  (15 routes)
- Not automatically verified: the real Gemini Live browser↔Google WebSocket path requires a
  working `GEMINI_API_KEY` supplied by the user — see docs/DECISIONS.md ADR-035 for the manual
  verification checklist

### Phase 6 — Semantic Retrieval + Deterministic Feasibility Engine

- `EmbeddingAdapter` interface (`src/adapters/embedding.py`): `GeminiEmbeddingAdapter`
  (`google-genai` SDK, `gemini-embedding-2`, configurable `GEMINI_EMBEDDING_DIMENSIONS`,
  asymmetric query/document prompting) and `MockEmbeddingAdapter` (deterministic
  hash/token-feature vector, not random, not ML). Selected by the same
  `GEMINI_ENABLED`+`GEMINI_API_KEY` rule as `AIAdapter` (`src/core/embedding.py`)
- `ExperienceEmbedding` model (`src/models/embedding.py`) — portable JSON column on SQLite;
  Phase 6 Alembic migration additionally adds a real `pgvector` column + HNSW cosine index on
  PostgreSQL (dialect-branched in one migration, never a separate Postgres-only migration)
- Canonical text builders (`src/services/embedding_text.py`) — document text from only real
  stored Experience fields (never fabricates rating/hours/availability/accessibility); query
  text from semantic-intent fields only (never budget/duration/travel/capacity — those stay
  exclusively FeasibilityService's job)
- `scripts/index_embeddings.py` — idempotent backfill/refresh script (`--limit --force
  --dry-run --only-missing`), content-hash change detection, per-record failure handling
  (failed = stays missing, never a fake success). Manually verified against the seeded dev DB
  (5 experiences: first run wrote 5, second run skipped all 5 as unchanged, `--force` re-wrote
  all 5, no duplicate rows)
- `SemanticRetrievalService` (`src/services/semantic_retrieval.py`) — query → embed → candidate
  pool → SAFE deterministic pre-filters only (active status, category, city/locality; never
  budget/hours/etc.) → candidate pool. Three honestly-reported `retrieval_mode` values:
  `pgvector_semantic` (Postgres, NOT VERIFIED live), `sqlite_python_semantic` (SQLite, bounded
  candidate load + Python cosine similarity — verified), `keyword_fallback` (reuses the
  existing Phase 4 `ExperienceDiscoveryService`, never a second search algorithm)
- `FeasibilityService` (`src/services/feasibility.py`) — 100% deterministic, zero LLM calls.
  Implements: active status, budget (INR-only, no currency conversion), duration, distance
  (Haversine), travel time (OSRM via the existing `RoutingAdapter`), total time (travel +
  experience duration vs. available window), opening hours (`ExperienceOpeningHour`,
  timezone-aware via `zoneinfo`, overnight/midnight-crossing windows), availability
  (`ExperienceAvailability`, slot containment), group size/capacity, accessibility (only when
  explicitly requested, only from stored `wheelchair_accessible`/`step_free`), and itinerary
  conflicts (plain `CommittedTimeBlock` interval input — no `Itinerary` model, that's Phase 8).
  Tri-state verdict (FEASIBLE/INFEASIBLE/UNKNOWN); UNKNOWN can never become FEASIBLE; all
  applicable checks run (never stops at first failure)
- Centralized reason-code enum (`src/core/feasibility_reasons.py`) — only implemented codes
- `DiscoveryPipelineService` (`src/services/discovery_pipeline.py`) — retrieval → feasibility
  gate → only FEASIBLE candidates in `items`, plus an excluded-candidate reason summary
  (counts by code, capped sample). All-excluded returns empty `items`, never a forced result
- `POST /api/v1/experiences/semantic-search` and `POST /api/v1/feasibility/check` — both
  require authentication (matches the Phase 4/5 convention exactly), Pydantic schemas only,
  never raw ORM
- `check_feasibility` added as the second Gemini tool (`CHECK_FEASIBILITY_DECLARATION`/
  `execute_check_feasibility`), registered in the Live token's `live_connect_constraints` tool
  list and the voice tool-call bridge's allowlist. Its argument schema has no field for
  price/hours/capacity/availability — Gemini cannot supply an invented value for any of those;
  the tool always loads the real `Experience` row. The Live system instruction (now actually
  attached to `LiveConnectConfig` — Phase 5's ADR-037 documented this policy but the adapter
  had not yet wired it into the SDK call) explicitly limits the model to the two real tools and
  forbids phrasing UNKNOWN as reassuring
- Text-turn orchestration (`handle_text_turn`) routes through `DiscoveryPipelineService`
  instead of the plain keyword tool whenever the extracted `TravelerContext` carries a hard
  constraint, producing a templated reply from real feasible/excluded counts — still one
  Gemini call per turn, still no free-form LLM feasibility verdict
- `TravelerContext` extended with optional, nullable Phase 6 fields only — every Phase 5 field
  and caller is unchanged
- Frontend: TypeScript types for `SemanticSearchRequest/Response`, `FeasibilityVerdict`,
  `FeasibilityReason`, `RetrievalMode` (`types/api.ts`), an API client
  (`lib/api/feasibility.ts`), and pure display-mapping functions
  (`lib/feasibility/feasibilityDisplay.ts`) with 15 Vitest unit tests — badge/reason-code
  mapping only, no visual redesign (kept modest per phase scope; see Partial below)
- 74 new backend tests (246 total) — feasibility engine (41 tests: every check's
  pass/fail/unknown/boundary case, multi-failure, tri-state precedence), retrieval→feasibility
  integration (3-candidate scenario: over-budget/all-pass/outside-hours → only the all-pass
  candidate survives; plus an all-excluded-returns-empty case), cosine similarity consistency
  (hand-computed values), embedding adapter/text builders, `check_feasibility` tool (real
  verdict, 404 on unknown id, validation rejects a fabricated price/hours field), semantic
  search + feasibility-check API endpoints — all passing alongside `ruff` (0 new issues; 6
  pre-existing E501s in Phase 2/3 auto-generated migrations untouched) and `mypy --strict`
  (0 issues)
- Alembic migration `6762a731d1f1_experience_embeddings` — verified against a fresh SQLite DB
  and the existing seeded dev DB (upgrade/downgrade/upgrade round-trip; 353 experiences / 311
  providers / 1 user / 1 conversation confirmed unaffected). **PostgreSQL path NOT VERIFIED —
  no PostgreSQL instance available in this environment**

---

### Phase 7 — Real ML Ranking + Feedback Learning

- `TravelerAffinity`/`Interaction` models implemented and synced to DB.
- Backend tracking of interactions (views, saves, etc.).
- Deterministic personalized weighted ranking with behavioral feedback learning (`WeightedPersonalizedRanker`), combining semantic relevance, affinities, preferences, and constraints.
- Real feedback loops calculating exponentially decayed recency-weighted affinities.
- `POST /api/v1/recommendations` and `POST /api/v1/feedback/interactions` endpoints deployed.
- Frontend components: `FeedbackControls`, `PersonalizationBadge` wired into `ExperienceCard` and `ExperienceDetail`.
- 100% of pipeline tests extended to cover scoring math and Phase 7 integrations.
- **Phase 8 preflight fixes** (found and corrected before Phase 8 work began, see docs/DECISIONS.md
  ADR-045 family and CHANGELOG.md 2026-09-24): `POST /api/v1/recommendations` was completely broken
  end-to-end (`get_embedding_adapter(settings)` called with an argument the singleton doesn't accept;
  `RecommendationResponse.excluded_summary` type mismatch); `DiscoveryPipelineService.run_with_ranking`
  crashed on `self._retrieval.session` (private attribute); `WeightedPersonalizedRanker` crashed
  building `RankedExperienceItem` (wrong/missing field set); the voice tool-call bridge crashed the
  same way as the endpoint. All fixed; a new regression test
  (`tests/test_pipeline_single_execution.py`) proves retrieval+feasibility execute exactly once per
  logical request for both the direct endpoint and the conversational tool path.

---

### Phase 8 — Deterministic Itinerary Composition with Gemini Narrative Generation

- `ExperienceComposerService` (`src/services/experience_composer.py`): deterministic two-stage
  composition (greedy selection + bounded local-improvement pass) over already-ranked,
  already-FEASIBLE Phase 7 candidates. No external optimizer.
- `ItineraryValidatorService` (`src/services/itinerary_validator.py`): mandatory post-composition
  validation reusing `FeasibilityReasonCode`; runs before any narrative and before persistence.
- `ItineraryNarratorService` (`src/services/itinerary_narrator.py`): Gemini narrative generation via
  the existing `AIAdapter`, facts-only prompt, anti-hallucination system instruction, deterministic
  template fallback on any Gemini failure.
- Models: `Itinerary`, `ItineraryItem`, `BookingRequest` (migration `8a004268dcb0`, verified against
  fresh SQLite; **PostgreSQL path NOT VERIFIED — no PostgreSQL instance available**).
- APIs: `POST /api/v1/itineraries/compose`, `GET /api/v1/itineraries`, `GET /api/v1/itineraries/{id}`,
  `POST /api/v1/itineraries/{id}/items`, `DELETE /api/v1/itineraries/{id}`,
  `POST /api/v1/itineraries/{itinerary_id}/booking-requests`, `GET /api/v1/bookings/me`,
  `GET /api/v1/provider/booking-requests`, `PATCH /api/v1/provider/booking-requests/{id}`,
  `POST /api/v1/bookings/{id}/cancel`.
- `compose_experience` Gemini tool added alongside `search_experiences`/`check_feasibility`; reuses a
  new `ConversationSession.last_search_candidates` cache so it never re-runs the Phase 6+7 pipeline
  redundantly when a candidate context already exists (regression-tested).
- Booking lifecycle is REQUESTED-only — no `CONFIRMED` status exists anywhere in the schema, and no
  payment fields exist anywhere in the model/schema/API surface.
- Frontend: `lib/api/itineraries.ts`, `lib/api/bookings.ts`, `lib/itinerary/itineraryDisplay.ts` (pure
  display helpers, tested), `ItineraryComposerForm`, `BookingRequestButton`, `RealItineraryTimeline`
  components wired into `/trip`.
- Full backend suite green (298 tests). Frontend `tsc --noEmit`/`lint`/`vitest`/`build` all green.

---

## Partial

- Backend ranking is currently configured as a deterministic heuristic rule set (weighted sums) due
  to no active model training infrastructure (wait for Phase 10 insights and telemetry scale-out).
- Phase 8 real (live, network) Gemini narrative generation: **LIVE VERIFIED** as of the 2026-09-25
  live debugging session — a real Gemini-narrated multi-stop itinerary was composed end to end
  (see CHANGELOG.md 2026-09-25 entries and ADR-054/ADR-055). The deterministic template fallback
  path remains fully tested and unchanged.
- Phase 8's manual "add item to an existing itinerary" endpoint
  (`POST /api/v1/itineraries/{id}/items`) builds a lightweight stand-in `RankedExperienceItem` for
  validation purposes (source_ranking_score is null) since a manually-added item was never part of a
  Phase 7 ranked candidate set — this is by design, not a bug, but is worth flagging as a narrower
  code path than the composer's main flow.

### Phase 9 — Real-Time Context + Events + Dynamic Replanning — Complete

Real-time weather/event context, deterministic impact detection, dynamic itinerary replanning, and
live SSE update delivery, built on top of the Phase 6/7/8 pipeline without duplicating any of it.

- `src/adapters/weather.py` — `OpenWeatherAdapter` (real, OpenWeather Current Weather Data + 5-Day
  Forecast REST endpoints), `MockWeatherAdapter` fallback. Shared httpx client, `IntervalRateLimiter`,
  `TTLCache`, typed errors — same pattern as OSRM/Nominatim. `WeatherContext` normalized shape;
  LIVE/CACHED/MOCK/UNAVAILABLE explicit. **LIVE VERIFIED** (2026-09-25 reconciliation) — a real
  request with a real `OPENWEATHER_API_KEY` returned real weather data; also confirmed the key
  itself is redacted (`appid=***REDACTED***`) in server logs. Also verified via
  `tests/test_weather_adapter.py` (fake HTTP client, 11 tests: normalization, malformed response,
  timeout/401/403/429/5xx, cache, mock fallback).
- `src/adapters/events.py` — `TicketmasterEventAdapter` (real, Ticketmaster Discovery API v2),
  `SeedEventAdapter` fallback (always `is_synthetic=true`, `source="seed"`, never fabricates a live
  event). `ExternalEventStatus` normalized strictly from `dates.status.code` — never inferred from
  missing data. **LIVE VERIFIED** (2026-09-25 reconciliation) — a real request with a real
  `TICKETMASTER_API_KEY` returned real event data; also confirmed the key itself is redacted
  (`apikey=***REDACTED***`) in server logs. Also verified via `tests/test_event_adapter.py`
  (13 tests).
- `src/services/weather_impact.py` — `WeatherImpactService`, deterministic
  WEATHER_GOOD/CAUTION/UNSUITABLE/UNKNOWN verdicts from `Experience.environmental_type` /
  `weather_sensitivity` / `weather_policy` (new, backward-compatible, default-UNKNOWN columns) +
  forecast + configurable thresholds (`Settings.weather_*_threshold*`).
- `src/services/context_impact.py` — `ContextImpactService`, compares previous vs new weather/event
  context against remaining itinerary items; NONE/LOW/MEDIUM/HIGH/CRITICAL/UNKNOWN severity with
  hysteresis (only a strictly-worse verdict than last-known triggers impact, so GOOD→CAUTION→GOOD does
  not flap). Never itself reorders anything — advisory only.
- `src/services/replanning.py` — `ReplanningService.replan_itinerary()`, the exact 13-step algorithm
  from the Phase 9 spec: preserves completed/in-progress/locked-future items, runs exactly one fresh
  Phase 6 retrieval+feasibility / Phase 7 ranking / Phase 8 composition pass for the remaining segment,
  full re-validation via the existing `ItineraryValidatorService`, versioned revision on success. Never
  a second ranking engine or discovery pipeline.
- `src/models/itinerary_revision.py`, `src/models/context_snapshot.py` — new tables (migration
  `04763f8eec67`, head was `8a004268dcb0`). `Itinerary` extended with `version` /
  `current_revision_id` / `replanning_status` / `context_last_updated_at`; `ItineraryItem` extended
  with `is_locked` / `item_state`. `Experience` extended with `environmental_type` /
  `weather_sensitivity` / `weather_policy` (all default UNKNOWN/NONE — never invented for existing
  rows).
- `POST /api/v1/itineraries/{id}/replan` (manual, traveler-only, `expected_version` optimistic lock →
  409 `ITINERARY_VERSION_CONFLICT` on mismatch, `idempotency_key` → no duplicate revision),
  `GET /api/v1/itineraries/{id}/updates` (SSE, require_traveler + ownership-checked, 404 on
  wrong-owner — never-disclose-existence), `GET /api/v1/context/weather`,
  `GET /api/v1/context/events` (read-only, authenticated, normalized data only).
- `src/services/ai_tools.py` — fourth Phase 9 Gemini tool, `replan_experience`; Task 4 later adds a fifth, read-only preview tool
  (`REPLAN_EXPERIENCE_DECLARATION` + `execute_replan_experience`), registered in `src/core/ai.py`'s
  tool list and the Live system instruction (`src/adapters/ai.py`). Never accepts traveler_id; never
  mutates the itinerary directly — only calls `ReplanningService`.
- `src/services/context_monitor.py` — `ContextMonitor`, one shared instance per process (in-process
  double-start guard), injectable clock, polling interval scales with proximity to itinerary start
  time. **Known limitation, explicitly documented, not solved**: this is single-process only — no
  distributed lock/leader-election, matching the current single-uvicorn-process architecture
  (`scripts/dev.ps1`/`dev.sh`); a future multi-worker production deployment would need one.
- `apps/web/lib/api/itineraryUpdates.ts` + `apps/web/hooks/useItineraryUpdates.ts` — SSE client (raw
  fetch+ReadableStream, not `EventSource`, because the endpoint needs a Bearer header `EventSource`
  cannot send) with capped-exponential-backoff reconnect. `RealItineraryTimeline.tsx` extended with a
  live-plan badge, last-updated time, replan-in-progress/requires-action states, and a "what changed"
  summary — the frontend never computes weather impact, event conflicts, or reordering itself.
- Backend: 360/360 tests pass (298 pre-Phase-9 baseline + 62 new). Frontend: 56/56 vitest tests pass,
  `tsc --noEmit` clean, `next build` succeeds, ESLint clean.
- Migration `04763f8eec67` verified upgrade→downgrade→upgrade against a fresh SQLite DB in this
  worktree, plus a full `scripts/seed.py` run against the migrated schema. **PostgreSQL explicitly NOT
  VERIFIED** — no Postgres instance in this isolated worktree (same honesty convention as Phase 6/7/8).

---

### Live Debugging Session — 2026-09-25

The first real end-to-end run of the deployed app (register/login, Discover map, voice, itinerary
composition) in a real browser, surfacing several bugs the automated test suite couldn't catch —
each required a genuinely running server, seeded data, or browser inspection to find. Full detail
in `docs/CHANGELOG.md`'s 2026-09-25 entry; `docs/DECISIONS.md` ADR-054 covers the feasibility/
composer correctness fix specifically. Summary:

- **Config**: blank (not unset) `JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET` broke all
  login/register; `GEMINI_MODEL_TEXT` switched from a persistently-503ing `gemini-3.8-flash` to
  `gemini-2.5-flash`.
- **Gemini structured output**: `TravelerContext`'s `response_schema` used Pydantic keywords
  (`exclusiveMinimum`, `additionalProperties`) Gemini's API rejects outright — every real
  conversational turn was silently falling back to keyword-only discovery. Fixed via a new
  `_gemini_safe_schema()` helper in `src/adapters/ai.py`.
- **Map**: MapLibre never painted tiles — its worker bundle's own internal import of a sibling
  file was missing from the `public/maplibre/` copy used to work around a Turbopack dev-server
  gap, so the worker died silently with zero real tile requests ever firing.
- **Voice transcript**: showed only the last few words of a reply (Gemini Live streams deltas,
  not cumulative text; the merge logic was replacing instead of appending).
- **Auth loading hang**: `RequireRole`-gated pages (Trips/Saved/Provider) hung on the loading
  skeleton forever on every fresh page load — a `bootstrapped` ref in `AuthContext.tsx` interacted
  badly with React Strict Mode's dev-only double-effect-invocation, guaranteeing the one bootstrap
  call that ran always saw its own cancellation flag already set by the time its (successful)
  network request resolved.
- **Error messaging**: generic "Validation failed"/"composed itinerary failed validation" strings
  replaced with messages built from the real per-field/per-reason data the API already returns
  (register form, itinerary composer form).
- **Narrative copy**: the Gemini narrator was told a `booking_status=not_requested` fact for
  every single itinerary item, so it dutifully (and correctly, per its own instructions) narrated
  a repetitive "booking is currently not requested" line on every item. Fixed to omit the fact
  when there's nothing to report.
- **Demo data completeness** (not code bugs, but blocked every real feature test): zero
  `ExperienceEmbedding` rows (ran `scripts/index_embeddings.py`: 341/353 embedded) and zero
  `ExperienceAvailability` rows anywhere in the catalog (new idempotent
  `scripts/seed_availability.py`: 810 slots derived from real opening hours across 65
  experiences).
- **Feasibility/composer correctness** (real logic bugs — see ADR-054): the composer's whole-day
  candidate gate was reusing single-visit-verification opening-hours/availability logic that
  required full-day containment, which almost no real venue can satisfy; and the mandatory
  post-composition validator's rejections were never retried against an alternative candidate
  even when one existed. Both fixed; verified end to end with a real Gemini-narrated multi-stop
  itinerary.
- All fixes verified against the full test suite throughout: backend 360/360, frontend 56/56,
  `tsc`/ESLint clean.

---

### Phase 0-9 Reconciliation — 2026-09-25

A full-codebase verification pass (not a new feature phase): `mypy --strict`/`ruff` across the
whole backend, live smoke tests against real Gemini/OpenWeather/Ticketmaster credentials, and a
full backend + frontend test/build verification. Full detail in `docs/CHANGELOG.md`'s 2026-09-25
reconciliation entry; `docs/DECISIONS.md` ADR-055 covers rationale for all findings below.

- Found and fixed four real bugs never caught by the existing test suite: the ranking budget
  filter never applying (`ranking.py`), API keys leaking into plaintext logs (`logging.py`), a
  replanning crash on offset-naive/aware datetime comparison plus a `sequence_order` collision
  (`replanning.py`), and unvalidated stored conversation context crashing tool-call ranking
  (`conversation.py`).
- Found and fixed the root cause of ~15+ silently-vacuous tests: the `discovery_dataset` test
  fixture had zero opening-hours/availability rows, so composition always failed and guarded
  assertions never ran. Fixed by seeding real data into the fixture.
- Diagnosed and worked around a genuine SSE `TestClient`/ASGI-transport hang (not an app bug —
  confirmed via live curl against a real server) by invoking the route's real logic directly in
  that one test, without opening a `TestClient` stream.
- **Backend**: `python -m pytest -q` → 361 passed, 0 failed, 0 hangs, 65.06s.
- **Frontend**: `tsc --noEmit` clean, `eslint` clean, `vitest run` → 56/56 passed (7 files),
  `next build` → succeeded (15 routes: 11 static, 4 dynamic).
- **Security sweep**: no hardcoded secrets found in tracked source; root `.env` confirmed
  untracked by git.
- **PostgreSQL: NOT VERIFIED** — no Postgres instance available in this environment; all
  verification above ran against the dev SQLite database, consistent with every earlier phase.

---

## Planned

### Phase 10 — Provider Intelligence & Two-Sided Marketplace
- Provider analytics dashboard
- Demand signal aggregation
- Traveler–provider matching
- Provider insight reports

### Phase 11 — Safety & Emergency
- Isolated Safety module
- Emergency contact management
- Nearby safety resource lookup
- Alert/notification mechanism

### Phase 12 — Full Integration, Testing, Hardening & Deployment
- End-to-end integration tests
- Performance testing
- Security audit
- Vercel frontend deployment
- FastAPI container deployment
- Supabase/PostgreSQL production setup
- Demo environment hardening

---

## Not Implemented

- Payments of any kind (Phase 8 booking is REQUESTED intent only — no Stripe/Razorpay, no card
  storage, no payment intent; a provider can ACCEPT/DECLINE but that is never a payment event)
- Real-time GPS turn-by-turn navigation (route preview only)
- Discover page UI wiring for the semantic-search pipeline endpoint (types/API client/display
  logic exist and are tested; the page itself doesn't call it yet — see Partial above)
- Multi-worker/multi-process `ContextMonitor` coordination (distributed lock/leader election) — this
  codebase runs single-process; documented as a limitation, not implemented, since nothing in this
  repo currently needs it.
- SSE event replay on reconnect — a reconnecting client gets a fresh `connected` event and new events
  going forward, but this in-process pub/sub bus keeps no backlog buffer for events published while
  disconnected (single-process, hackathon-scope limitation).

---

## Task 3 — Public Social Signal Integration (PARTIAL, 2026-09-27)

- Added the backend Bluesky adapter, deterministic classifier, normalized
  signal model, bounded in-memory aggregate cache, and authenticated
  `GET /api/v1/twin/social-signals` endpoint.
- Added an explicit Social Pulse action and accessible aggregate panel to
  the existing itinerary map. It uses the shared `MapSurface` and existing
  geocoder/API patterns; it does not replace map, weather, or routing.
- Raw posts and author identifiers stay inside the adapter; only aggregate
  topic clusters reach the API response. The map pin marks the selected
  search center, not a post coordinate. Social signals never change itinerary
  state or trigger replanning.
- No database migration, durable post storage, Nugen dependency, or social
  ingestion pipeline was added. At Task 3 integration, `/twin` was a read-only
  API namespace; Task 4 later adds a separate, ephemeral `/digital-twin`
  what-if preview flow.
- The current Bluesky public-search request was blocked with HTTP 403, and
  the already-running API process did not load the new route. Source-level
  API tests pass, but the local API must be restarted before the running web
  app can use the endpoint. Full live-provider/UI verification remains open.

## Task 4 Add-on — What-if Simulation and Traveler Review

The additive simulation layer is implemented on top of the existing itinerary,
weather/context, OSRM routing, discovery, social, and replanning services. A
preview is read-only and ephemeral; applying requires an explicit traveler
action and delegates to `ReplanningService` with the captured itinerary
version. The `DomainIntelligenceProvider` is a protocol plus mock only; no
Nugen runtime or social ingestion was added.

- API: `POST /api/v1/digital-twin/itineraries/{id}/simulate` and
  `POST /api/v1/digital-twin/simulations/{id}/apply`.
- Preview inputs and outputs keep weather, route, experience, and social
  assumptions labelled; social aggregates remain advisory. Alternative lookup
  is bounded and reuses the existing discovery/ranking pipeline.
- Preview sessions live in a bounded (256-entry), 15-minute in-process cache;
  restart clears them and multiple API workers do not share them.
- No database migration or new persistent itinerary state is required.
- Backend health and OpenAPI route smoke checks pass, and the existing Discover
  MapLibre map renders in the browser. Full authenticated itinerary preview/apply
  verification remains pending because the browser is logged out. Automated
  test details are recorded in `docs/CHANGELOG.md`.

## Known Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Gemini Live API rate limits or quota | High | Ephemeral token architecture; mock fallback for dev |
| SQLite → PostgreSQL migration breaks | Medium | Use only portable SQLAlchemy constructs from Day 1; Phase 6 migration verified fresh + seeded SQLite |
| LLM hallucinating feasibility | Critical | `FeasibilityService` is 100% deterministic (zero LLM calls) |

---

## Current Next Milestone

**Phase 10 — Provider Intelligence & Two-Sided Marketplace**

Phase 9 (real-time context + events + dynamic replanning) is Complete — see above. Phase 10 has not
started.
