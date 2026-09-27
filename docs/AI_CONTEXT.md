# LocaLens — AI Agent Context File

> **READ THIS FIRST before modifying any code in this repository.**
> This file is the primary orientation document for AI coding agents.
> Last updated: 2026-09-25 | Current phase: Phases 0-9 Complete (reconciliation pass) | Phase 10 not started

---

## What LocaLens Is

LocaLens is an AI-powered local experience discovery and matching platform built for HackCelestial 3.0 (PS-6).

It connects travelers and local experience providers through:
- Natural language and voice interaction (Gemini Live)
- Deterministic feasibility checking (not LLM-based)
- Personalized ML ranking
- AI-assisted experience composition
- Dynamic replanning when conditions change
- Two-sided marketplace (Traveler + Provider)

The core product loop: **understand → retrieve → verify feasibility → personalize → compose → adapt → learn**

---

## Current Stack

| Layer | Technology | Version |
|---|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS, App Router | Next.js 16.x |
| Backend | Python, FastAPI, Pydantic v2 | FastAPI 0.141+ |
| ORM | SQLAlchemy (async) | 2.0.x |
| Migrations | Alembic | latest |
| Database (dev) | SQLite + aiosqlite | — |
| Database (prod) | PostgreSQL + asyncpg, Supabase | — |
| AI | Google Gemini (text + Live voice), `google-genai`/`@google/genai` SDKs | gemini-2.5-flash / gemini-3.8-live |
| Maps | MapLibre GL JS, OSM, Nominatim, OSRM | — |
| Weather | OpenWeather (adapter-based) | — |
| Events | Ticketmaster adapter + seed events | — |

---

## Repository Structure

```
/
├── apps/
│   ├── web/          ← Next.js frontend (Phase 1+)
│   └── api/          ← FastAPI backend (Phase 1+)
├── docs/             ← Architecture, contracts, decisions, roadmap
│   ├── AI_CONTEXT.md          ← YOU ARE HERE
│   ├── ARCHITECTURE.md        ← Full architecture document
│   ├── PRODUCT_CONTRACT.md    ← Product purpose, users, capabilities
│   ├── PROJECT_STATE.md       ← Current implementation status
│   ├── DECISIONS.md           ← Architectural decision records
│   ├── TASKS.md               ← Phase-based task backlog
│   ├── ROADMAP.md             ← Phase roadmap
│   └── CHANGELOG.md           ← Change history
├── scripts/          ← Developer utility scripts
├── tests/            ← Cross-app integration tests
├── .env.example      ← Environment variable contract
├── .gitignore
└── README.md
```

---

## Architecture Summary

```
Traveler / Provider
      ↓
API Layer (FastAPI)
      ↓
Context & Intent Engine (Gemini LLM)
      ↓
Experience Discovery Engine
      ↓
Constraint & Feasibility Engine ← DETERMINISTIC ONLY — no LLM here
      ↓
Personalized Ranking Engine
      ↓
AI Experience Composer (Gemini LLM — post-feasibility only)
      ↓
Personalized Output
      ↓
Feedback & Learning Engine
      ↓ (on real-time changes)
Dynamic Replanning Engine → loops back to feasibility check
```

External adapters (all behind interface boundaries):
- `AIAdapter` — Gemini text generation (structured TravelerContext extraction) and ephemeral
  Live token issuance (`GeminiAIAdapter` / `MockAIAdapter`, Phase 5)
- `GeocodingAdapter` — Nominatim
- `RoutingAdapter` — OSRM
- `POIAdapter` — Overpass API
- `WeatherAdapter` — OpenWeather
- `EventAdapter` — Ticketmaster / seed events
- `MapTilesAdapter` — MapTiler / OSM

---

## Module Ownership

| Module | Phase | Status |
|---|---|---|
| Context & Intent Engine | 5 | IMPLEMENTED (text: LIVE VERIFIED; voice: Gemini Live + search_experiences tool, NOT VERIFIED — needs real browser mic session) |
| Experience Discovery Engine | 4 | IMPLEMENTED (deterministic keyword/filter/radius — not ML) |
| Constraint & Feasibility Engine | 6 | IMPLEMENTED (SQLite LIVE VERIFIED; PostgreSQL/pgvector NOT VERIFIED) |
| Personalized Ranking Engine | 7 | IMPLEMENTED (see ADR-055 for a budget-filter bug found and fixed this reconciliation) |
| AI Experience Composer | 8 | IMPLEMENTED (Gemini narrative LIVE VERIFIED; PostgreSQL migration path NOT VERIFIED) |
| Dynamic Replanning Engine | 9 | IMPLEMENTED (see ADR-055 for datetime and sequence_order bugs found and fixed this reconciliation) |
| Feedback & Learning Engine | 7 | IMPLEMENTED |
| Provider Intelligence | 10 | PLANNED (UI shell IMPLEMENTED) |
| Safety & Emergency Module | 11 | PLANNED (UI shell IMPLEMENTED) |
| Authentication & Roles | 3 | IMPLEMENTED |
| Provider profile & experience/availability CRUD | 3 | IMPLEMENTED (owner-only) |
| Database models & migrations | 2/3 | IMPLEMENTED |
| Open data ingestion (Overture Places) | 2 | IMPLEMENTED |
| Experience read API | 4 | IMPLEMENTED (full search/filter/radius/sort — Phase 2 read API extended) |
| Geocoding adapter (Nominatim) | 4 | IMPLEMENTED |
| Routing/travel-time adapter (OSRM) | 4 | IMPLEMENTED |
| Nearby-POI adapter (Overpass) | 4 | IMPLEMENTED |
| Map rendering (MapLibre GL JS + OpenFreeMap) | 4 | IMPLEMENTED |
| UI system & design | 1 | IMPLEMENTED |
| API foundation | 1 | IMPLEMENTED |

---

## Critical Invariants — Never Violate These

### INV-1: LLM is never the final feasibility authority
The Constraint & Feasibility Engine makes all hard constraint decisions.
The LLM may summarize, explain, or assist composition — never decide feasibility.

### INV-2: Infeasible experiences are rejected before ranking
The ranking engine only receives verified-feasible candidates.

### INV-3: No business logic in React components
All business logic lives in application services on the backend.
Frontend components call APIs; they do not contain domain logic.

### INV-4: All external services behind adapter interfaces
No direct calls to Gemini, Nominatim, OSRM, OpenWeather, or any external API
from within application services or UI components.
All calls go through typed adapter interfaces.

### INV-5: GEMINI_API_KEY must never reach the browser
The FastAPI backend issues short-lived ephemeral tokens for Gemini Live sessions.
The master API key stays server-side only.

### INV-6: Database queries must be portable
No SQLite-specific syntax. All queries must work on PostgreSQL.

### INV-7: Safety module is architecturally isolated
The Safety & Emergency Module does not depend on any recommendation system component.

### INV-8: Synthetic/demo data is always labelled
Any seed or synthetic data includes explicit markers (e.g., `is_synthetic: true`).

### INV-9: No hardcoded golden demo path
Intelligence must emerge from the general architecture.
Mumbai/Fort area may be used as seed data, but logic must generalize.

### INV-10: Honest feature status
Always use: IMPLEMENTED / PARTIAL / PLANNED / NOT IMPLEMENTED.
Never mark a placeholder as IMPLEMENTED.

### INV-11: Tokens never persist in browser storage
The access token lives only in memory (`apps/web/lib/auth/tokenStore.ts`) —
never `localStorage`, `sessionStorage`, or IndexedDB. The refresh token is
never readable by JavaScript at all — only an HttpOnly cookie. See
docs/DECISIONS.md ADR-019.

### INV-12: Ownership is always server-derived, never client-supplied
`provider_id` (or any ownership field) is never accepted from a request
body. It always comes from the authenticated user loaded server-side.
See docs/DECISIONS.md ADR-021.

### INV-13: Catalog/synthetic/registered provider data must never be blurred
A provider row's lineage (`source_type`) determines what it may do:
catalog-imported and synthetic providers have no `user_id` and can never
log in; only `source_type="registered"` providers are real accounts.
Reseeding the Overture/synthetic catalog must never delete or renumber
registered accounts' data. See docs/DECISIONS.md ADR-021.

### INV-14: The LLM never invents catalog facts or fabricates a booking
Gemini (text or Live) must never invent an experience name, price,
rating, duration, opening hours, availability, or travel time — every
fact it discusses must come from a real `search_experiences` result (or,
as of Phase 8, a real `check_feasibility`/`compose_experience` result).
Gemini can trigger a real `compose_experience` booking-adjacent itinerary
(Phase 8), but it never confirms a booking itself — booking state is
always REQUESTED/ACCEPTED/DECLINED as returned by the backend, never a
free-form claim. See docs/DECISIONS.md ADR-035, ADR-046, ADR-047.

### INV-15: search_experiences/check_feasibility/compose_experience are
the only Gemini tools, and only the backend executes them
The browser is a transport/UI layer for Gemini Live — it forwards a
`tool_call` verbatim to `POST /conversations/{id}/tool-calls` and relays
the real result back via `sendToolResponse`. It never implements
discovery/feasibility/composition logic itself, and no tool name outside
this three-tool allowlist is ever accepted. See docs/DECISIONS.md
ADR-035/ADR-036/ADR-044/ADR-048.

### INV-16: GEMINI_API_KEY is backend-only; only ephemeral tokens reach
the browser
The master key never appears in browser code, bundles, logs, or
responses. The browser only ever holds a short-lived ephemeral token
(from `POST /api/v1/auth/live-token`), in memory only. See
docs/DECISIONS.md ADR-035.

### INV-17: Public social signals are opt-in, area-level, and advisory
Bluesky content is queried only after an explicit traveler action, parsed
inside the backend adapter, and reduced to short-lived aggregate clusters.
Never return raw post text, author IDs/handles, or post URLs to the normal
frontend; never infer a post coordinate or let a social signal trigger
automatic re-planning. These signals are unverified context, not facts.
See docs/DECISIONS.md ADR-058.

---

## Current Implementation Status

**Phase**: PHASE 5 — Conversational AI + Gemini Live Voice Agent

**IMPLEMENTED (Phase 1/2 — carried forward):**
- Next.js 16 (App Router, TypeScript strict, Tailwind CSS v4) frontend; FastAPI backend
- Async SQLAlchemy 2.0 + Alembic; hybrid Overture Places + synthetic catalog (353 experiences,
  311 providers, 20 categories, 353 locations); `GET /api/v1/experiences` + `/{id}` + `/categories`

**IMPLEMENTED (Phase 3 — carried forward):**
- JWT auth: HS256 access token (~15 min, memory-only) + refresh token (~7 days, HttpOnly cookie,
  distinct secret) — `src/core/security.py`, `src/core/cookies.py`
- `AuthSession` model — hashed refresh tokens, rotation on every `/auth/refresh`, reuse detection
  (revokes all sessions for the user), logout revocation — `src/models/auth_session.py`
- `POST /api/v1/auth/{register,login,refresh,logout}`, `GET /api/v1/auth/me`
- Role system (`traveler`/`provider`/`admin`) with centralized dependencies
  (`get_current_user`, `require_role`, `get_current_provider`) in `src/core/deps.py` — ADMIN
  cannot self-register; `scripts/create_admin.py` is the only way to create one (env-driven)
- Provider profile API (`GET/PUT /api/v1/providers/me`), owner-scoped experience list
  (`GET /api/v1/providers/me/experiences`)
- Provider-owned Experience CRUD (`POST /api/v1/experiences`, `PATCH/DELETE /{id}` — soft-delete
  via `status="inactive"`) — `provider_id` always server-derived, never client-supplied
- `ExperienceAvailability` model + CRUD (`/api/v1/experiences/{id}/availability/*`), owner-scoped,
  public read
- Explicit provider lineages never blurred: catalog-imported/synthetic providers have no
  `user_id`; only `source_type="registered"` providers are real accounts (see ADR-021)
- `scripts/seed.py` reseeds only Overture/synthetic rows — registered accounts' data and shared
  categories (now upserted by slug) survive every reseed (a real bug found and fixed in Phase 3)
- Frontend: `AuthProvider`/`useAuth` (`lib/auth/AuthContext.tsx`), in-memory token store
  (`lib/auth/tokenStore.ts`), typed API client with automatic 401-refresh-retry, real login/
  register forms, role-aware nav, `proxy.ts` optimistic route guard, provider dashboard + full
  experience/availability management UI backed by the real API

**IMPLEMENTED (Phase 4 — new):**
- `GET /api/v1/experiences` extended: keyword/category/price/duration/lat+lng+radius_km/sort
  filters, deterministic non-personalized relevance scoring
  (`src/services/discovery.py::ExperienceDiscoveryService`) — explicitly not ML/AI
- Portable Haversine + bounding-box radius search (`src/core/geo.py`) — no PostGIS/spatial
  extension, works identically on SQLite (dev) and PostgreSQL (prod); see ADR-022
- Real adapters: `NominatimGeocodingAdapter`, `OSRMRoutingAdapter`, `OverpassPOIAdapter`
  (`src/adapters/{geocoding,routing,poi}.py`) — each rate-limited (`IntervalRateLimiter`) and
  TTL-cached (`TTLCache[T]`) per its own usage policy; see ADR-023/024/025/030
- `LOCATION_SERVICES_ENABLED` kill switch — falls back to existing `Mock*Adapter`s; catalog
  discovery keeps working with real DB results even when all three external services are off;
  see ADR-031
- `GET /api/v1/location/{search,reverse,nearby-pois}`, `POST /api/v1/location/{route,
  travel-time-matrix}` (`src/api/v1/location.py`) — the only path to Nominatim/Overpass/OSRM;
  the browser never calls them directly
- Travel-time/distance enrichment on `GET /experiences` always labels its source
  (`travel_time_source: "osrm" | "haversine_estimate"`) — never presented as exact when
  estimated; see ADR-024
- Frontend: real MapLibre GL JS map (`components/common/MapSurface.tsx`, replacing the Phase 1
  placeholder) with OpenFreeMap tiles, clustered GeoJSON experience source (never one DOM marker
  per result — ADR-027), "Search this area" bounds-triggered re-query that never auto-fires on
  pan/zoom alone (ADR-028)
- URL-synchronized discovery state (`?q=&category=&lat=&lng=&radius_km=&sort=` —
  `lib/discovery/urlState.ts`, ADR-029); explicit-trigger-only geolocation/place search
  (`hooks/useUserLocation.ts`, `hooks/useLocationSearch.ts` — never auto-requested, never
  server-persisted, see ADR-032)
- Experience detail page: "Set a starting point" + "Show route" using the real routing adapter
- 142 backend tests total for Phase 4 — all passing alongside `ruff`/`mypy --strict`; frontend
  `lint`/`tsc --noEmit`/`build` all pass

**IMPLEMENTED (Phase 5 — new):**
- `GeminiAIAdapter` (`src/adapters/ai.py`) — real `google-genai` SDK, `generate_content` with
  Pydantic `response_schema` for structured `TravelerContext` extraction, `auth_tokens.create`
  for ephemeral Live tokens with `live_connect_constraints` locking model/tools/system
  instruction server-side. `MockAIAdapter.generate_text` rewritten to a graceful deterministic
  keyword extraction (never raises); `issue_live_token` still fails loudly — voice is never
  faked. `src/core/ai.py` DI provider mirrors the Phase 4 `location.py` pattern
- `TravelerContext`/`SearchExperiencesArgs`/`SearchExperiencesResult` schemas
  (`src/schemas/conversation.py`) shared by both text and voice paths — one structured-intent
  model, not two parallel schemas
- `search_experiences` — the only Gemini tool this phase (`src/services/ai_tools.py`); a thin
  wrapper around the existing `ExperienceDiscoveryService`, zero new search logic
- Text-mode orchestration (`src/services/conversation.py`) — one Gemini call per turn
  (extraction only), bounded recent-history window, deterministic template assistant reply
  (never a second free-form Gemini call, so text prose can never fabricate result claims)
- `ConversationSession`/`ConversationMessage` models — user-owned, cascade-deleted, transcript
  text only (audio never persisted); new Alembic migration verified against a fresh DB and the
  existing seeded DB (353 experiences/311 providers unaffected)
- `POST /api/v1/conversations`, `POST /conversations/{id}/messages`, `GET /conversations/{id}`,
  `POST /conversations/{id}/tool-calls` (the voice-path bridge — the only place
  `search_experiences` actually executes); ownership 404s for another user's conversation
- `POST /api/v1/auth/live-token` — `require_traveler`-gated, issues a short-lived ephemeral
  Gemini Live token; `GEMINI_API_KEY` never leaves the backend, the token is never logged/persisted
- Frontend: real AudioWorklet-based 16-bit/16kHz PCM mic capture, 24kHz scheduled PCM playback
  with barge-in support, `GeminiLiveClient` (transcription, tool-call bridge, session
  resumption, GoAway handling) — `lib/voice/*`, `public/worklets/pcm-capture-worklet.js`
- `ConversationalDiscoveryInput.tsx`'s Phase 1 permanently-disabled mic button is now a real
  voice control; text submit now runs a real conversational turn; `DiscoverExperience.tsx`
  threads a `Partial<DiscoveryState>` patch callback (app-controlled translation, never the
  model — `lib/discovery/travelerContextToPatch.ts`, `location_text` never auto-geocoded)
- 30 new backend tests (172 total) — AI adapter (mock + real against a fake SDK client, no real
  network), conversation service/API (ownership isolation, tool validation), live-token
  (role gate, mock-always-503, real-shape success) — all passing alongside `ruff`/`mypy --strict`
- Vitest newly introduced for the frontend (previously no test framework existed) — 20 targeted
  tests for the discovery-patch translator and PCM encode/decode/resample math; `tsc --noEmit`,
  `eslint`, `next build` (15 routes) all pass

**IMPLEMENTED (Phase 6 — new):**
- `EmbeddingAdapter` (`src/adapters/embedding.py`) — `GeminiEmbeddingAdapter` (real
  `google-genai` SDK, `gemini-embedding-2`, asymmetric query/document prompting; **NOT
  VERIFIED live — no API key**) and `MockEmbeddingAdapter` (deterministic, not random),
  selected by the same rule as `AIAdapter`
- `ExperienceEmbedding` model + Alembic migration `6762a731d1f1` — portable JSON column
  (verified on SQLite fresh + seeded DB); dialect-branched pgvector column + HNSW index on
  PostgreSQL (**NOT VERIFIED live — no PostgreSQL instance**)
- `scripts/index_embeddings.py` — idempotent, content-hash-based, per-record failure isolation
- `SemanticRetrievalService` — embed → candidates → SAFE pre-filters only (status/category/
  city, never budget/hours/etc.); honest `retrieval_mode` reporting
  (`pgvector_semantic`/`sqlite_python_semantic`/`keyword_fallback`)
- `FeasibilityService` (`src/services/feasibility.py`) — 100% deterministic, zero LLM calls;
  tri-state FEASIBLE/INFEASIBLE/UNKNOWN verdict; covers active status, budget, duration,
  distance, travel time, total time, opening hours (timezone-aware, overnight-aware),
  availability, capacity, accessibility, itinerary conflicts (plain interval input, no
  persisted model)
- `DiscoveryPipelineService` — retrieval → feasibility hard gate; only FEASIBLE candidates in
  `items`; excluded-candidate reason summary; all-excluded returns empty, never a forced result
- `POST /api/v1/experiences/semantic-search`, `POST /api/v1/feasibility/check`
- `check_feasibility` — second Gemini tool; schema has no field for price/hours/capacity/
  availability, so Gemini cannot supply an invented fact; backend-owned execution only, exactly
  like `search_experiences`
- Live system instruction now actually attached to `LiveConnectConfig` (this closes a real gap:
  Phase 5's ADR-037 documented the policy but the adapter had not yet wired it into the SDK call)
- `TravelerContext` extended with optional, nullable Phase 6 fields — additive only
- 74 new backend tests (246 total), 15 new frontend tests (35 total) — all passing alongside
  `ruff`/`mypy --strict` (backend) and `tsc --noEmit`/`eslint`/`next build` (frontend)

**PARTIAL:**
- Weather/Events adapters (`apps/api/src/adapters/weather.py`, `events.py`) are now REAL
  implementations (Phase 9, OpenWeather + Ticketmaster Discovery API) — verified only against a
  fake HTTP client in this worktree, **NOT VERIFIED live** (no API keys available here). MapTiles
  remains Protocol + mock only (out of Phase 9 scope)
- `/provider/insights` remains Phase 1 mock data, explicitly labelled — real analytics is Phase 10
- Gemini Live's real browser↔Google WebSocket path is implemented end-to-end but has not been
  manually verified with a working `GEMINI_API_KEY` as of this writing — see ADR-035's manual
  checklist. Automated tests prove the application-side contract without needing real credentials
- Real Gemini embedding generation (`GeminiEmbeddingAdapter`) — implemented against the
  documented SDK surface, **NOT VERIFIED live** (no API key available in this environment)
- PostgreSQL/pgvector semantic retrieval path — implemented (migration + repository query),
  **NOT VERIFIED live** (no PostgreSQL instance available in this environment)
- Phase 6 frontend: types/API client/pure display-mapping functions exist and are tested; the
  Discover page itself is not yet wired to call `/experiences/semantic-search` or render
  verified-match badges/excluded summaries in the browser

**PLANNED:**
- Everything else (see docs/ROADMAP.md)

**NOT IMPLEMENTED:**
- Provider claiming (a real business claiming its catalog-imported record), password reset,
  email verification, social login, MFA, full admin dashboard, booking/payments, provider
  analytics backend, real-time GPS turn-by-turn navigation
- (As of Phase 9: ranking, feedback learning, AI composer/itinerary generation,
  `Itinerary`/`ItineraryItem` persistence, dynamic replanning, and weather/events integration ARE
  now implemented — see docs/PROJECT_STATE.md Phase 7/8/9 sections. This list entry is kept for
  historical accuracy of the Phase 6 snapshot it was originally written against; do not read it as
  current status for those items.)

---

## Current Known Limitations

- Database is SQLite in local dev; no PostgreSQL/Supabase instance has been provisioned yet
  (the models and queries are written to be portable — see docs/DECISIONS.md ADR-005/006)
- `apps/web/proxy.ts` only checks refresh-cookie *presence* for an optimistic redirect — it does
  not verify the cookie, so a browser must use the same hostname (`localhost` vs `127.0.0.1`) for
  the frontend and any manually-tested API calls, or cookies won't be recognized as matching
- Next.js response streaming (routes with a `loading.tsx` boundary) means some "not found" cases
  return an initial HTTP 200 shell before the client renders the 404 UI — a framework trade-off
  noted in the Phase 2 changelog, not a routing defect
- OSRM's public demo server and the public Overpass instance have no uptime SLA — the app
  degrades gracefully (Haversine estimate / empty POI results) rather than failing, but a live
  demo may occasionally show a fallback state if either service is under load; see ADR-024/025
- No weather or event integrations — deferred to their respective phases (AI/conversational
  discovery is now real as of Phase 5, map/location as of Phase 4, see above)
- Gemini Live's real audio round-trip requires a working `GEMINI_API_KEY` in `.env` — with
  `GEMINI_ENABLED=false` or no key, text discovery still works via `MockAIAdapter`'s
  deterministic extraction, but voice clearly reports unavailable rather than connecting
- Live session WebSocket connections are capped at roughly 10 minutes by the Gemini Live API
  itself regardless of session-resumption configuration — `GeminiLiveClient` reconnects
  proactively on `goAway`, but a very long single voice session will still see a brief
  `RECONNECTING` state

---

## How to Safely Modify This Repository

### Before any change:
1. Check `docs/PROJECT_STATE.md` for current phase status
2. Confirm the change belongs to the current or an already-started phase
3. Check `docs/DECISIONS.md` to ensure you are not contradicting a recorded decision

### When adding a new module:
1. Define its interface (Python Protocol or TypeScript interface) first
2. Implement the concrete class behind that interface
3. Create a mock/fallback implementation for development
4. Register the adapter/service in the dependency injection layer
5. Update `docs/PROJECT_STATE.md` status

### When modifying the database:
1. Never edit existing Alembic migration files
2. Always create a new migration: `alembic revision --autogenerate -m "description"`
3. Ensure models use standard SQLAlchemy types — no SQLite-only types

### When working with AI/Gemini:
1. All Gemini calls go through `AIAdapter` interface
2. Never put `GEMINI_API_KEY` in frontend code
3. For Live voice: use the ephemeral token endpoint (`POST /auth/live-token`)
4. Never trust LLM output for feasibility decisions
5. Any Gemini tool must be backend-executed and explicitly allowlisted by name — the browser
   only ever forwards a `tool_call` to the backend and relays the real result back
6. Never add a new Gemini tool without updating all of: its `*_DECLARATION` registration in
   `src/core/ai.py`'s tool list, the `/tool-calls` route's allowlist, and (if it should be
   voice-callable) the Live system instruction's list of permitted tools — `search_experiences`
   and `check_feasibility` are the two currently implemented and registered this way

### When adding a new experience:
1. Include: `is_synthetic: true/false`
2. Include: opening hours, capacity, accessibility info (even if null initially)
3. Ensure experience has at least one location coordinate

### When adding external API calls:
1. Create or implement the appropriate adapter interface
2. Add a mock fallback for when the API key is absent
3. Add the API key to `.env.example` with a comment
4. Never hardcode API URLs — use configuration

---

## Gemini Live Tool Contract (Phase 5/6 — IMPLEMENTED)

The voice agent calls application tools — it never invents results. Two
tools are implemented and registered in the Live session config
(`src/services/ai_tools.py`):

- `search_experiences` (`SEARCH_EXPERIENCES_DECLARATION`) — calls the
  existing `ExperienceDiscoveryService` via
  `execute_search_experiences`. The browser forwards Gemini's
  `tool_call` to `POST /api/v1/conversations/{id}/tool-calls`; that
  endpoint is the only place the tool actually executes.
- `check_feasibility` (`CHECK_FEASIBILITY_DECLARATION`, Phase 6) — calls
  the deterministic `FeasibilityService` via `execute_check_feasibility`.
  Its argument schema (`CheckFeasibilityArgs`) has no field for price,
  opening hours, capacity, or availability — Gemini can supply only an
  `experience_id` and constraint context (budget/time/party
  size/travel/accessibility); the tool always loads the real
  `Experience` row from the database, so a fabricated fact in the model's
  tool call is structurally impossible to inject, not merely discouraged.

Any tool name other than `search_experiences`/`check_feasibility`/
`compose_experience`/`replan_experience`/`simulate_what_if` is rejected
(422) by that endpoint — the model can never trigger arbitrary application
behavior. The Live system instruction (locked into the ephemeral token's
`live_connect_constraints`) explicitly restricts the model to these five
tools and forbids phrasing an UNKNOWN feasibility verdict as reassuring
or a REQUESTED booking as confirmed.

`compose_experience` (Phase 8, `src/services/ai_tools.py`) composes a
chronological, travel-aware itinerary from experiences
`search_experiences` already returned in the same conversation — it
validates every `experience_id` Gemini supplies against
`ConversationSession.last_search_candidates` (never trusting a raw id
blindly) and triggers at most one fresh Phase 6+7 pipeline pass when no
candidate context yet exists (never a redundant second pass otherwise).
It never confirms a booking; booking state is always the real backend
`BookingRequest.status`.

`replan_experience` (Phase 9, `src/services/ai_tools.py`) is the fourth
tool. It never accepts `traveler_id`, provider authorization,
final itinerary state, or a booking confirmation from Gemini — it
accepts only `itinerary_id`, an optional `affected_experience_id` hint
(always revalidated), a free-text `requested_change`, and optional
time/budget/party-size hints, and delegates entirely to
`ReplanningService.replan_itinerary()` — the exact same call the manual
`POST /itineraries/{id}/replan` REST endpoint makes. It never directly
edits the itinerary and never decides weather suitability, event
cancellation, schedule conflicts, or itinerary validity itself — only
narrates the structured `ReplanResponse` the backend returns, including
honestly reporting `REPLAN_FAILED`/`REQUIRES_USER_ACTION` outcomes.

`simulate_what_if` (Task 4, `src/services/ai_tools.py`) is a fifth,
read-only tool for traveler-requested hypothetical previews. The authenticated
conversation derives traveler ownership server-side. It returns an ephemeral,
bounded preview and never applies or persists a proposed itinerary change.
Weather, route, experience, and social assumptions stay labelled as
hypothetical or advisory; the tool does not decide safety or feasibility. Only
the traveler can explicitly apply a still-current preview through the UI,
which delegates to the existing `ReplanningService.replan_itinerary()` path.
The preview session is held in a bounded in-process TTL cache, so it is lost on
process restart and is not shared across multiple API workers.

`get_weather`/`get_events` as standalone Gemini tools were considered for
Phase 9 and deliberately NOT implemented — weather/event context reaches
the itinerary only through the deterministic
`WeatherImpactService`/`ContextImpactService` pipeline inside
`ReplanningService`, never as a fact Gemini could fetch and narrate
directly (external event/weather text is untrusted data, never placed
directly into a system instruction — see the SYSTEM RULES / TRAVELER
REQUEST / VALIDATED ITINERARY DATA / EXTERNAL CONTEXT DATA prompt
structure `ItineraryNarratorService` and `replan_experience` follow).

`save_experience`/`create_booking_request` as standalone Gemini tools
remain explicitly NOT implemented — saving is automatic on a successful
`compose_experience`/`POST /itineraries/compose`, and booking-request
creation is a direct API call rather than a conversational tool.

See docs/DECISIONS.md ADR-035/ADR-036/ADR-037/ADR-044 through ADR-053 and ADR-057 through ADR-059
for the full architecture and security rationale.
