# LocaLens — Task Backlog

> High-signal phase-based task backlog.
> Tasks are categorized by phase and priority.
> Low-level implementation details are tracked in GitHub Issues / sprint boards (not here).
> Last updated: 2026-09-25

---

## P0 — Reset, Baseline & Master Contract

- [x] Inspect project folder and confirm clean state
- [x] Initialize git repository
- [x] Create `.gitignore` (Python, Node, Next.js, SQLite, secrets, IDEs)
- [x] Create `.env.example` with full environment contract
- [x] Create `README.md` (human + AI agent orientation)
- [x] Create `docs/AI_CONTEXT.md` (AI agent context + invariants)
- [x] Create `docs/ARCHITECTURE.md` (full logical architecture)
- [x] Create `docs/PRODUCT_CONTRACT.md` (product purpose, users, capabilities)
- [x] Create `docs/PROJECT_STATE.md` (current implementation status)
- [x] Create `docs/DECISIONS.md` (16 architectural decision records)
- [x] Create `docs/TASKS.md` (this file)
- [x] Create `docs/ROADMAP.md` (13-phase roadmap with gates)
- [x] Create `docs/CHANGELOG.md` (initial changelog entry)
- [x] Create directory placeholders for `apps/web/`, `apps/api/`, `scripts/`, `tests/`
- [x] Verify repository structure is clean and consistent

---

## P1 — Application Foundation & UI System

> **Target**: Working dev environment with both apps running. No business logic.
> **Status**: ✅ Complete (2026-09-22)

### Frontend (apps/web/)
- [x] Initialize Next.js 16 project (`npx create-next-app@latest`)
- [x] Configure TypeScript (strict mode)
- [x] Configure Tailwind CSS v4
- [x] Establish color palette and design tokens
- [x] Create root layout component (`app/layout.tsx`)
- [x] Create shell/navigation components (header, mobile tab bar)
- [x] Create page templates (traveler, provider)
- [x] Create typed API client (`lib/api/client.ts`)
- [x] Configure `NEXT_PUBLIC_API_BASE_URL` environment handling
- [x] Responsive layout foundations (mobile + desktop)
- [x] Add Google Font (Plus Jakarta Sans, geometric sans)
- [x] Create `app/page.tsx` (full landing page — hero, loop, examples, composer preview, provider CTA)

### Backend (apps/api/)
- [x] Initialize FastAPI project structure
- [x] Configure Pydantic v2 settings (env-based config)
- [x] Create `GET /api/v1/health` endpoint
- [x] Create CORS middleware configuration
- [x] Create application factory (`create_app()`)
- [x] Define project module structure (`api/`, `adapters/`, `core/`)
- [x] Create adapter interfaces (Python Protocol) for all external services
- [x] Create mock implementations for all adapters
- [x] Create environment startup validation (warn on missing optional keys; fail on required)

### Developer Experience
- [x] Configure `pyproject.toml` / `requirements.txt` with pinned versions
- [x] Configure `package.json` scripts for dev (`npm run dev`)
- [x] Linting: Ruff (Python), ESLint (TypeScript)
- [x] Type checking: mypy --strict (Python), `tsc --noEmit` (TypeScript)
- [x] Add `scripts/dev.sh` and `scripts/dev.ps1` to start both apps

---

## P2 — Database, Models, Open Data Ingestion & Realistic Experience Data

> **Target**: Queryable database with a real-open-data + synthetic hybrid catalog.
> **Status**: ✅ Complete (2026-09-22)

### Database & models
- [x] Configure SQLAlchemy async engine factory (`apps/api/src/core/db.py`)
- [x] Configure Alembic (async-compatible; `apps/api/alembic/`)
- [x] Create shared mixins: `UUIDPrimaryKeyMixin`, `TimestampMixin`, `ProvenanceMixin`
- [x] Model: `User` (id, email, password_hash, role, is_active)
- [x] Model: `Traveler` (user_id, traveler_type, preferences, accessibility_requirements)
- [x] Model: `Provider` (business_name, provider_type, verification_status, provenance)
- [x] Model: `ExperienceCategory` (slug, name, description, icon, sort_order)
- [x] Model: `Location` (lat, lng, place_name, address, locality, city, provenance)
- [x] Model: `Experience` (full field set — see `apps/api/src/models/experience.py`)
- [x] Model: `ExperienceOpeningHour` (day_of_week, open_time, close_time, is_closed)
- [x] Generate + verify initial Alembic migration against a fresh database

### Overture Maps ingestion
- [x] Research current official Overture docs/tooling (DuckDB spatial/httpfs, no API key)
- [x] `scripts/ingest_overture.py` — Mumbai bbox query, category allowlist, confidence threshold
- [x] `src/core/category_map.py` — 20-category LocaLens taxonomy + Overture category mapping
- [x] Deduplication (source_record_id, normalized-name + proximity) and validation
- [x] Provenance extraction (source dataset, record id, license) preserved per record
- [x] Ingestion report (raw/accepted/rejected counts by reason) written to `data/processed/`

### Synthetic layer & seeding
- [x] `scripts/synthetic_data.py` — templated, deterministic, clearly labelled synthetic data
- [x] `scripts/seed.py` — full reseed: categories, Overture-derived + synthetic providers/experiences
- [x] Verify seed data runs clean on a fresh database (353 experiences, 311 providers, 20
      categories, 353 locations, 0 duplicate source IDs)

### API & frontend integration
- [x] `ExperienceRepository`/`ProviderRepository`/`CategoryRepository`/`LocationRepository`
- [x] Pydantic response schemas (`schemas/experience.py`) — no SQLAlchemy model exposed directly
- [x] `GET /api/v1/experiences` (category/city/status/limit/offset) + `GET /api/v1/experiences/{id}`
- [x] Discover page + detail page render database-backed data with loading/error states
- [x] `data/README.md` — full provenance, licensing, and attribution documentation

### Tests
- [x] Database/session/relationship tests, ingestion pure-function tests, synthetic-data
      determinism tests, API list/detail/pagination/filter/404 tests (27 total, all passing)

---

## P3 — Authentication, Roles & Provider Foundation

> **Target**: Secure API; providers can create listings.
> **Status**: ✅ Complete (2026-09-22)

### Backend — auth
- [x] JWT access (~15 min, memory-only) + refresh (~7 days, HttpOnly cookie) token implementation
- [x] `POST /api/v1/auth/register` (traveler and provider; ADMIN rejected)
- [x] `POST /api/v1/auth/login`
- [x] `POST /api/v1/auth/refresh` (rotation + reuse detection)
- [x] `POST /api/v1/auth/logout` (session revocation)
- [x] `GET /api/v1/auth/me`
- [x] `AuthSession` model — hashed refresh tokens, rotation, revocation
- [x] Argon2 password hashing (`pwdlib`)
- [x] Role enum: `TRAVELER`, `PROVIDER`, `ADMIN`
- [x] Role-based route guards (`get_current_user`, `require_role`, `get_current_provider`)
- [x] `scripts/create_admin.py` — env-driven, the only way to create an ADMIN account

### Backend — provider & experience CRUD
- [x] `GET/PUT /api/v1/providers/me` (provider profile)
- [x] `GET /api/v1/providers/me/experiences` (owner-scoped list)
- [x] `GET /api/v1/categories`
- [x] `POST /api/v1/experiences` (provider creates listing; `provider_id` server-derived)
- [x] `PATCH /api/v1/experiences/{id}` (owner-only; protected fields excluded)
- [x] `DELETE /api/v1/experiences/{id}` (owner-only soft-delete → `status="inactive"`)
- [x] `ExperienceAvailability` model + full CRUD endpoints (owner-scoped mutations, public read)
- [x] Fixed a Phase 2 seed-script bug that would have wiped registered accounts on reseed

### Frontend
- [x] `AuthProvider`/`useAuth`, in-memory token store, automatic 401-refresh-retry API client
- [x] Real login/register forms wired to the API
- [x] Role-aware navigation (`SiteHeader`)
- [x] `apps/web/proxy.ts` — optimistic route guard for `/trip`, `/saved`, `/provider*`
- [x] Provider dashboard connected to real data (no fabricated analytics)
- [x] `/provider/experiences` full CRUD UI (`ExperienceForm`, `AvailabilityManager`)

### Tests
- [x] 45 new tests (72 total): registration/login/refresh-rotation/reuse-detection/logout, role
      authorization, provider/availability ownership isolation, catalog-experience protection,
      CORS/cookie flags, seed-safety — all passing alongside `ruff`, `mypy --strict`, frontend
      `lint`/`tsc --noEmit`/`build`

---

## P4 — Experience Discovery, Catalog & OSM Location Layer

> **Target**: Experiences discoverable via location + basic filters + map view.
> **Status**: ✅ Complete (2026-09-22)

- [x] `GET /experiences` (search, filter, paginate, location radius)
- [x] `GET /experiences/{id}` (detail — already existed from Phase 2, unchanged)
- [x] `GeocodingAdapter` interface + Nominatim implementation + mock
- [x] `RoutingAdapter` interface + OSRM implementation + mock
- [x] `POIAdapter` interface + Overpass implementation + mock
- [x] Location radius search (portable Haversine + bounding-box, no PostGIS — see ADR-022)
- [x] MapLibre GL JS map component (frontend, replacing the Phase 1 placeholder)
- [x] Experience pins on map (clustered GeoJSON source, not per-marker DOM nodes)
- [x] Experience detail page location/route section (frontend)
- [x] Category filter UI (chips, carried forward + wired to real filter params)
- [x] Distance + travel time display (honestly labelled `osrm` vs `haversine_estimate`)
- [x] `GET/POST /api/v1/location/{search,reverse,nearby-pois,route,travel-time-matrix}`
- [x] `LOCATION_SERVICES_ENABLED` kill switch + Mock adapter fallback
- [x] URL-synchronized discovery state (`?q=&category=&lat=&lng=&radius_km=&sort=`)
- [x] "Search this area" — map pan/zoom never auto-triggers a re-query
- [x] 70 new backend tests (142 total) — geo math, discovery, adapters (fake HTTP client, no real
      network calls in the suite), location API, categories — all passing alongside `ruff`,
      `mypy --strict`, frontend `lint`/`tsc --noEmit`/`build`
- [x] `data/README.md` §9 — Nominatim/Overpass/OSRM/MapLibre/OpenFreeMap attribution & scope
- [x] `docs/DECISIONS.md` ADR-022 through ADR-032

---

## P5 — Conversational AI + Gemini Live Voice Agent

> **Target**: Traveler can describe request in text or voice; system returns relevant experiences.
> **Status**: ✅ Complete (2026-09-22), pending user's manual live-key verification

- [x] `AIAdapter` interface + `GeminiAIAdapter` + `MockAIAdapter` (graceful text fallback,
      voice always fails loudly rather than faking a connection)
- [x] `TravelerContext` Pydantic schema (scoped to Phase 5 needs — understanding + retrieval,
      not itinerary/feasibility), shared by text and voice paths
- [x] Structured-output prompt for intent extraction → `TravelerContext` (one Gemini call per
      text turn; `response_mime_type`/`response_schema`)
- [x] `POST /api/v1/conversations` + `POST /api/v1/conversations/{id}/messages` (text turn)
- [x] Conversation session model (`ConversationSession`/`ConversationMessage`, user-owned,
      cascade-deleted, transcript text only — no audio persisted)
- [x] `GET /api/v1/conversations/{id}` (bounded history)
- [x] `POST /api/v1/auth/live-token` (`require_traveler`-gated ephemeral token for Gemini Live,
      `live_connect_constraints` locks model/tools/system instruction server-side)
- [x] Real voice UI (`components/voice/`, `hooks/useVoiceAgent.ts`) — AudioWorklet PCM capture,
      scheduled PCM playback with barge-in, `@google/genai` browser SDK Live connection
- [x] Gemini function/tool calling integration (session resumption, GoAway handling,
      transcription)
- [x] Tool: `search_experiences` (thin wrapper around the existing `ExperienceDiscoveryService`
      — zero new search logic) — the only Gemini tool this phase
- [x] `POST /api/v1/conversations/{id}/tool-calls` — the voice-path bridge; the only place
      `search_experiences` actually executes, never the browser
- [x] End-to-end: text/voice input → intent extraction → real experience results →
      `DiscoveryState` patch (app-controlled translation, never the model)
- [x] 30 new backend tests (172 total), 20 new frontend Vitest tests (framework newly
      introduced) — all passing alongside `ruff`/`mypy --strict`/`tsc --noEmit`/`eslint`/`build`
- [ ] Manual verification with a real `GEMINI_API_KEY` (browser↔Google Live audio round-trip) —
      requires the user's own key; see docs/DECISIONS.md ADR-035

---

## P6 — Semantic Retrieval + Constraint / Feasibility Engine

> **Target**: Semantic search active. Infeasible experiences never reach ranking.

- [x] Experience embedding generation (Gemini embedding model) — `GeminiEmbeddingAdapter`
      implemented against the documented `google-genai` SDK surface; **NOT VERIFIED live — no
      `GEMINI_API_KEY` available**. `MockEmbeddingAdapter` (deterministic) verified via the full
      test suite and `scripts/index_embeddings.py` run against the seeded dev DB
- [x] pgvector setup (Supabase / production migration) — Alembic migration branches per-dialect
      (`CREATE EXTENSION IF NOT EXISTS vector`, `vector(1536)` column, HNSW cosine index);
      **NOT VERIFIED live — no PostgreSQL instance available**
- [x] Semantic search endpoint — `POST /api/v1/experiences/semantic-search`, verified on SQLite
- [x] Keyword fallback for SQLite/dev mode — reuses the existing Phase 4
      `ExperienceDiscoveryService`, selected automatically when embeddings are
      unavailable/disabled or when the query text is empty
- [x] Feasibility Engine: opening hours check — timezone-aware (`zoneinfo`), handles
      overnight/midnight-crossing windows and closed days; missing data + required = UNKNOWN
- [x] Feasibility Engine: budget check — INR-only (no currency conversion); missing price +
      hard budget = UNKNOWN; mismatched currency = UNKNOWN
- [x] Feasibility Engine: travel time / distance check — Haversine for explicit max-distance;
      OSRM (existing `RoutingAdapter`) for travel time; OSRM unavailable + hard constraint =
      UNKNOWN, never substituted with Haversine
- [x] Feasibility Engine: group size / capacity check — real stored `capacity`/
      `maximum_group_size` only; missing + required = UNKNOWN
- [x] Feasibility Engine: accessibility check — only checked when explicitly requested; only
      from stored `wheelchair_accessible`/`step_free`; missing + required = UNKNOWN
- [x] Feasibility Engine: itinerary conflict check — plain `CommittedTimeBlock` interval input
      (deterministic interval arithmetic); no `Itinerary`/`ItineraryItem` persistence model
      (that's Phase 8's scope, per the phase brief)
- [x] Feasibility Engine: availability / provider availability check — real
      `ExperienceAvailability` slot containment; missing + required = UNKNOWN
- [x] Machine-readable rejection reason codes — centralized `FeasibilityReasonCode` enum
- [x] Tool: `check_feasibility` — second Gemini tool; backend-owned execution; schema has no
      field for price/hours/capacity/availability
- [x] Integration tests: verify no infeasible experience passes the filter —
      `tests/test_discovery_pipeline.py` (3-candidate scenario + all-excluded-returns-empty
      case); 41 additional unit tests cover every individual check

---

## P7 — Real ML Ranking + Feedback Learning ✅ Complete

> **Target**: Different traveler profiles produce meaningfully different rankings.

- [x] `Interaction` model (view, save, complete, skip, rate)
- [x] `TravelerPreference` model
- [x] `TravelerAffinity` model (per-category/tag affinity scores)
- [x] Feedback API (`POST /interactions`)
- [x] Personalized ranking algorithm (weighted scoring — deterministic, not embedding-based) — a
      real bug (budget filter reading a nonexistent `context.constraints.budget_max` instead of
      the flat `context.budget_max`) was found and fixed this reconciliation; see
      docs/DECISIONS.md ADR-055
- [x] Affinity update on new feedback
- [x] Ranking endpoint integrated into main discovery pipeline
- [x] Quality metric: A/B ranking comparison for different profiles

---

## P8 — Deterministic Itinerary Composition with Gemini Narrative Generation ✅ Complete

> **Target**: Valid time-ordered itinerary narrative produced from traveler context.

- [x] Composition algorithm (select + order + time-allocate) — `ExperienceComposerService`
- [x] `Itinerary` model
- [x] `ItineraryItem` model (experience, time_start, time_end, travel_gap)
- [x] Gemini narrative composer (post-feasibility only) — `ItineraryNarratorService`
- [x] Post-composition feasibility re-validation — `ItineraryValidatorService`
- [x] `POST /api/v1/itineraries/compose` (compose + save)
- [x] `GET /api/v1/itineraries`, `GET /api/v1/itineraries/{id}`
- [x] Booking request model + `POST /api/v1/itineraries/{itinerary_id}/booking-requests`
- [x] Tool: `compose_experience`
- [ ] Tool: `save_experience` (not in Phase 8 scope — itineraries are auto-saved on successful compose)
- [ ] Tool: `create_booking_request` (booking is a direct API call, not exposed as a separate Gemini tool in Phase 8)
- [x] Itinerary view UI (frontend) — `ItineraryComposerForm`, `RealItineraryTimeline`, `BookingRequestButton`
  wired into `/trip`; real Gemini narrative generation not live-verified (see PROJECT_STATE.md Partial)

---

## P9 — Real-Time Context + Events + Dynamic Replanning — Complete

> **Target**: Changing traveler context triggers a new valid plan within seconds.

- [x] `WeatherAdapter` interface + OpenWeather implementation + mock (`src/adapters/weather.py`) —
      real implementation NOT VERIFIED live (no API key in the implementing worktree)
- [x] `EventAdapter` interface + Ticketmaster implementation + seed fallback (`src/adapters/events.py`)
      — real implementation NOT VERIFIED live (no API key in the implementing worktree)
- [x] `ContextSnapshot` model (normalized weather/event audit record — `src/models/context_snapshot.py`)
- [x] `ExternalEvent` (adapter-level normalized dataclass, not persisted as its own table — kept
      distinct from `Experience` per the phase brief; events are candidate context, never
      auto-inserted into a catalog)
- [x] `ItineraryRevision` model (trigger + reason + normalized change set — `src/models/itinerary_revision.py`)
- [x] `WeatherImpactService` (`src/services/weather_impact.py`) + `ContextImpactService`
      (`src/services/context_impact.py`) — deterministic, no LLM involvement
- [x] Dynamic Replanning Engine (`src/services/replanning.py`, `ReplanningService`) — reuses Phase
      6/7/8 services directly, no second ranking/discovery/composer engine
- [x] Re-feasibility → re-rank → re-compose pipeline for the remaining segment only — completed/
      locked items never rewritten
- [x] SSE endpoint for live plan updates (`GET /api/v1/itineraries/{id}/updates`,
      `src/services/sse.py`) — WebSocket deliberately not used (no existing WS infra; see ADR-052)
- [x] Tool: `replan_experience` (`src/services/ai_tools.py`, fourth Phase 9 tool; Task 4 adds a read-only fifth tool)
- [ ] Tool: `get_weather` / `get_events` — deliberately NOT implemented as standalone Gemini tools;
      weather/event context reaches the plan only through the deterministic impact pipeline, never
      as a fact Gemini fetches and narrates directly (see docs/AI_CONTEXT.md)
- [x] Demo scenario: weather-aware replacement (outdoor item + heavy rain → detected, preserved
      unaffected items, remaining slot recomposed) — covered by
      `tests/test_phase9_end_to_end.py`, not a live-key demo run
- [x] Demo scenario: event time-change → conflict detected → replan — covered by
      `tests/test_phase9_end_to_end.py`/`tests/test_context_impact.py`, not a live-key demo run

---

## Task 4 Add-on — What-if Simulation and Traveler Review

> Additive geospatial/context preview for existing itineraries. This work does not replace
> existing map, weather, routing, discovery, social, or replanning systems.

- [x] Typed scenario, evidence, impact, result, and future domain-intelligence contracts
- [x] Bounded read-only simulation using existing weather, OSRM, social, and discovery services
- [x] Explicit hypothetical/advisory labels, route-unavailable fallback, and bounded alternatives
- [x] Authenticated preview/apply endpoints with ownership, TTL, and itinerary-version checks
- [x] Apply delegates to `ReplanningService`; preview never mutates the itinerary
- [x] Additive traveler UI and read-only conversational `simulate_what_if` tool
- [x] Backend and frontend regression suites pass; verification details are in the changelog
- [ ] Authenticated live preview/apply browser smoke verification (public map/API route smoke passed)
- [x] No migration; no Nugen runtime or new decision/ranking engine

---

## P10 — Provider Intelligence & Two-Sided Marketplace

> **Target**: Provider can see demand intelligence and traveler matches.

- [x] `DemandSignal` aggregation service
- [x] `ProviderInsight` model
- [x] Provider analytics API (`GET /providers/me/insights`)
- [x] Traveler–provider matching score
- [x] Provider notification: qualified traveler match
- [x] Provider analytics dashboard UI
- [x] Demand trend charts (views, saves, bookings over time)
- [x] "Synthetic Data" label enforcement in UI

---

## P11 — Safety & Emergency

> **Target**: Safety features functional independently of recommendation system.

- [x] Safety module isolation verified (no recommendation imports)
- [x] Emergency contact model + CRUD
- [x] Nearby safety resources endpoint (hospitals, police, consulates)
- [x] Emergency alert mechanism (notification or webhook)
- [x] Safety UI component (accessible, always-visible trigger)
- [x] Safety API: auth-only, no recommendation dependency

---

## P12 — Full Integration, Testing, Hardening & Deployment

> **Target**: Production-ready demo on real infrastructure.

- [ ] End-to-end integration test suite (Playwright for frontend, pytest for API)
- [ ] API performance testing (response time < 2s for all demo endpoints)
- [x] OWASP top 10 basic security review
- [ ] Vercel frontend deployment
- [ ] Docker containerization for FastAPI
- [ ] Cloud/container deployment for FastAPI (Render/Railway/GCP)
- [ ] Supabase production database setup
- [ ] pgvector enabled in production
- [ ] All `.env` variables configured in deployment platform
- [ ] Demo environment seed data loaded
- [ ] Synthetic data labels verified in production UI
- [ ] `docs/PROJECT_STATE.md` fully updated to IMPLEMENTED
- [ ] Final demo rehearsal and timing

---

## TASK 3 — Public Social Signal Integration (PARTIAL)

> **Target**: Show opt-in, area-level public context while preserving existing backend decision ownership.

- [x] Bluesky public-search adapter with bounded result count and request pacing
- [x] Deterministic topic classification and normalized internal signal model
- [x] Aggregate-only API contract with heuristic confidence, freshness, severity, and sparse-trend handling
- [x] Authenticated `GET /api/v1/twin/social-signals`, verified-area lookup, short in-memory aggregate cache, and explicit unavailable/rate-limited states
- [x] Social Pulse control and accessible aggregate panel in the existing itinerary map; requests only on explicit enable
- [x] No raw posts/accounts in the API response; no inferred post coordinates, database migration, Nugen dependency, or automatic replanning
- [ ] Live Bluesky search verification — current public endpoint request returned HTTP 403 in this environment
- [ ] End-to-end check against the active API — source changes are tested, but the running process must be restarted to load the route
- [ ] Manual visual browser smoke test after API restart

The repository did not contain a Digital Twin simulation service before this task. This work adds only a read-only social context extension point and does not claim simulation or what-if support.
