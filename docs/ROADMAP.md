# LocaLens — Roadmap

> 13-phase delivery roadmap for HackCelestial 3.0 — PS-6.
> Each phase builds on the previous. Phase boundaries are intentional gates.
> Last updated: 2026-09-25

---

## Phase Dependency Graph

```
PHASE 0 (Foundation)
    │
    ▼
PHASE 1 (App Foundation & UI System)
    │
    ▼
PHASE 2 (Database, Models & Seed Data)
    │
    ▼
PHASE 3 (Auth, Roles & Provider Foundation)
    │         │
    ▼         ▼
PHASE 4   PHASE 3 also enables Provider UI
(Discovery, Catalog & OSM Layer)
    │
    ▼
PHASE 5 (Conversational AI + Gemini Live Voice)
    │
    ▼
PHASE 6 (Semantic Retrieval + Feasibility Engine)
    │
    ▼
PHASE 7 (ML Ranking + Feedback Learning)
    │
    ▼
PHASE 8 (AI Composer + Itinerary + Booking)
    │
    ▼
PHASE 9 (Real-Time Context + Events + Replanning)
    │
    ▼
PHASE 10 (Provider Intelligence & Marketplace)
    │
    ▼
PHASE 11 (Safety & Emergency)     [can start after Phase 3]
    │
    ▼
PHASE 12 (Integration, Testing, Hardening & Deployment)
```

---

## Phase Descriptions

---

### PHASE 0 — Reset, Baseline & Master Contract

**Status**: ✅ Complete

**Goal**: Establish the engineering foundation before writing any application code.

**Deliverables**:
- Repository initialized
- Full documentation suite (all `docs/` files)
- Architectural contract established (13 invariant rules + 16 ADRs)
- Environment variable contract (`.env.example`)
- Project roadmap, task backlog, and changelog
- High-level source structure
- `.gitignore`
- `README.md`

**Phase Gate**: Architecture contract approved. Documentation complete.

---

### PHASE 1 — Application Foundation & UI System

**Status**: ✅ Complete

**Depends on**: Phase 0

**Goal**: Create working scaffolds for both apps; establish the design system.

**Deliverables**:
- `apps/web/`: Next.js 16 + App Router + TypeScript + Tailwind CSS
- `apps/api/`: FastAPI + Pydantic v2 structure
- Core layout components (shell, navigation, page templates)
- Typed API client layer (`apps/web/src/lib/api/`)
- `GET /health` endpoint
- Environment configuration validation (startup checks)
- Development server setup (both apps running concurrently)
- Responsive, accessible UI foundation

**Phase Gate**: Both dev servers run. `GET /health` returns 200. No business logic yet.

---

### PHASE 2 — Database, Models, Open Data Ingestion & Realistic Experience Data

**Status**: ✅ Complete

**Depends on**: Phase 1

**Goal**: Establish the database layer and a realistic hybrid (open-data + synthetic) dataset.

**Deliverables**:
- SQLAlchemy async engine + session factory; Alembic migration pipeline initialized
- Core models: User, Traveler, Provider, ExperienceCategory, Location, Experience,
  ExperienceOpeningHour, with a shared provenance mixin
- Overture Maps Places ingestion pipeline (Mumbai bbox, DuckDB spatial/httpfs, no API key)
- LocaLens category taxonomy (20 categories) + Overture category mapping
- Deduplication, validation, and provenance-preserving normalization
- Synthetic demo layer (templated, labelled) filling gaps open POI data cannot describe
- Seed script populating 353 experiences / 311 providers / 20 categories / 353 locations
- `GET /api/v1/experiences` + `GET /api/v1/experiences/{id}`, Pydantic schemas, repositories
- Discover UI connected to the live API
- `data/README.md` — full source, licensing, and attribution documentation

**Phase Gate**: Database migrates. Seed script runs. Experiences queryable via API. ✅ Met.

---

### PHASE 3 — Authentication, Roles & Provider Foundation

**Status**: ✅ Complete

**Depends on**: Phase 2

**Goal**: Secure the API and enable provider accounts and experience listings.

**Deliverables**:
- JWT authentication (memory-only access token + HttpOnly-cookie refresh token, rotation +
  reuse detection via `AuthSession`)
- Role system: TRAVELER, PROVIDER, ADMIN (ADMIN never self-registrable)
- User registration + login endpoints
- Provider profile creation and editing
- Experience CRUD (provider-owned, ownership always server-derived)
- Availability management (provider-side, `ExperienceAvailability` model)
- Route guards (frontend optimistic `proxy.ts` + authoritative FastAPI dependencies)
- Catalog-imported/synthetic provider lineages kept distinct from registered accounts

**Phase Gate**: A provider can register, create a listing, and set availability. Authentication
enforced. ✅ Met — see docs/PROJECT_STATE.md and the Phase 3 changelog entry.

---

### PHASE 4 — Experience Discovery, Catalog & OSM Location Layer

**Status**: ✅ Complete

**Depends on**: Phase 2, Phase 3

**Goal**: Make experiences discoverable via location and basic filters.

**Deliverables**:
- Experience catalog API (search, filter, paginate) — `GET /api/v1/experiences` extended with
  keyword/category/price/duration/radius/sort
- `GeocodingAdapter` (Nominatim) + mock fallback
- `RoutingAdapter` (OSRM) for travel time + mock fallback
- `POIAdapter` (Overpass) for nearby POI discovery + mock fallback
- Location-radius search endpoint — portable Haversine + bounding-box (ADR-022)
- MapLibre GL JS integration (frontend map view, OpenFreeMap tiles)
- Experience detail page location/route section

**Phase Gate**: Traveler can browse experiences on a map and filter by location radius. ✅ Met —
see docs/PROJECT_STATE.md and docs/DECISIONS.md ADR-022 through ADR-032.

---

### PHASE 5 — Conversational AI + Gemini Live Voice Agent

**Status**: ✅ Complete (pending user's manual live-key verification)

**Depends on**: Phase 4

**Goal**: Enable natural language and voice as the primary traveler interaction mode.

**Deliverables**:
- `AIAdapter` (`GeminiAIAdapter`, `gemini-2.5-flash`/`gemini-3.8-live` — text model switched from
  `gemini-3.8-flash` after persistent 503s, see docs/CHANGELOG.md 2026-09-25) + `MockAIAdapter`
  fallback
- `TravelerContext` structured schema, shared by text and voice
- Intent extraction from natural language → `TravelerContext` (one Gemini call per text turn)
- Conversational session management (server-side, `ConversationSession`/`ConversationMessage`)
- Ephemeral token endpoint (`POST /auth/live-token`) for Gemini Live, `live_connect_constraints`
  locking model/tools/system instruction server-side
- Real voice UI (`@google/genai` browser SDK, AudioWorklet PCM capture/playback)
- Gemini function/tool calling → application tools, backend-only execution
- Initial (and only) tool: `search_experiences` — reuses the Phase 4 discovery engine directly

**Phase Gate**: Traveler can describe a request in text or voice; system returns relevant
experiences. ✅ Met for text and the application-side voice contract (automated tests, no real
Gemini network calls); the real browser↔Google audio round-trip requires the user's own
`GEMINI_API_KEY` to manually verify — see docs/DECISIONS.md ADR-035.

---

### PHASE 6 — Semantic Retrieval + Constraint / Feasibility Engine

**Status**: ✅ Complete (real Gemini embedding + live pgvector verification pending — no API
key / no PostgreSQL instance available in this environment)

**Depends on**: Phase 5

**Goal**: Replace keyword search with semantic retrieval. Enforce deterministic feasibility.

**Deliverables**:
- Experience embedding generation (via Gemini embedding model) — implemented
  (`GeminiEmbeddingAdapter`, NOT VERIFIED live) + `MockEmbeddingAdapter` (verified)
- pgvector integration (Supabase/PostgreSQL) — migration + repository path implemented,
  NOT VERIFIED live
- Semantic search endpoint — `POST /api/v1/experiences/semantic-search`, verified on SQLite
- Keyword fallback for SQLite/dev mode — reuses the Phase 4 discovery service
- Deterministic Feasibility Engine (all constraint types) — active status, budget, duration,
  distance, travel time, total time, opening hours, availability, capacity, accessibility,
  itinerary conflicts; zero LLM calls; tri-state verdict
- Machine-readable rejection reason codes — centralized `FeasibilityReasonCode` enum
- Full pipeline: retrieval → feasibility → filtered candidates — `DiscoveryPipelineService`
- Feasibility tool for Gemini: `check_feasibility` — backend-owned, schema forbids invented facts

**Phase Gate**: ✅ Met — `DiscoveryPipelineService` only ever returns FEASIBLE candidates in
`items`; excluded candidates are summarized with reason codes; verified via
`tests/test_discovery_pipeline.py` and 41 `FeasibilityService` unit tests.

---

### PHASE 7 — Real ML Ranking + Feedback Learning

**Status**: ✅ Complete (deterministic personalized weighted ranking with behavioral feedback learning)

**Depends on**: Phase 6

**Goal**: Personalize recommendations and learn from traveler behavior.

**Deliverables**:
- Interaction tracking (views, saves, completions, skips, ratings)
- TravelerPreference + TravelerAffinity models
- Personalized ranking (initially weighted scoring; later embedding-based)
- Feedback API endpoints
- Feedback loop: interactions → affinity update → ranking improvement
- Recommendation quality metrics

**Phase Gate**: Two travelers with different affinity profiles receive meaningfully different rankings.

---

### PHASE 8 — Deterministic Itinerary Composition with Gemini Narrative Generation

**Status**: ✅ Complete (real live Gemini narrative call not exercised this session; PostgreSQL migration path NOT VERIFIED)

**Depends on**: Phase 7

**Goal**: Compose multiple feasible experiences into a coherent time-ordered plan.

**Deliverables**:
- Experience composition algorithm (greedy + optimization)
- Gemini LLM narrative composer (post-feasibility only)
- Post-composition feasibility re-validation
- Itinerary object model (ItineraryItem, time slots, travel gaps)
- Save itinerary to traveler profile
- Booking request flow (request intent; no full payment)
- Composer tool for Gemini: `compose_experience`

**Phase Gate**: From a traveler context, the system produces a validated, time-ordered itinerary narrative.

---

### PHASE 9 — Real-Time Context + Events + Dynamic Replanning

**Status**: ✅ Complete (OpenWeather + Ticketmaster adapters LIVE VERIFIED with real API keys this
reconciliation; a datetime-comparison replanning crash and a sequence_order UNIQUE constraint
collision bug were found and fixed — see docs/DECISIONS.md ADR-055)

**Depends on**: Phase 8

**Goal**: React to real-world changes and dynamically update plans.

**Deliverables**:
- `WeatherAdapter` (OpenWeather) + mock fallback
- `EventAdapter` (Ticketmaster / seed events) + fallback
- Real-time context update triggers
- Dynamic Replanning Engine
- Re-feasibility → re-rank → re-compose pipeline
- WebSocket or SSE for live plan update delivery
- Replanning tool for Gemini: `replan_experience`

**Phase Gate**: Changing traveler time or budget triggers a new valid plan within seconds.

---

### PHASE 10 — Provider Intelligence & Two-Sided Marketplace

**Status**: ✅ Complete

**Depends on**: Phase 7, Phase 9

**Goal**: Give providers actionable demand intelligence and traveler matching.

**Deliverables**:
- Provider analytics dashboard (views, saves, bookings, reviews)
- DemandSignal aggregation
- Traveler–provider matching scores
- ProviderInsight model
- Demand trend reports
- Provider notification for qualified traveler matches

**Phase Gate**: A provider can see which traveler types are interested and what demand looks like.

---

### PHASE 11 — Safety & Emergency

**Status**: ✅ Complete

**Depends on**: Phase 3 (auth)

**Goal**: Provide isolated safety features independent of all recommendation logic.

**Deliverables**:
- Safety module (isolated; no recommendation dependencies)
- Emergency contact management
- Nearby safety resource lookup (hospitals, police, consulates)
- Emergency alert/notification mechanism
- Safety resource API (read-only, auth-only)

**Phase Gate**: Safety features remain functional even if recommendation services are down.

---

### PHASE 12 — Full Integration, Testing, Hardening & Deployment

**Status**: ❌ Blocked (Missing real deployment credentials, Docker daemon, and Postgres)

**Depends on**: All previous phases

**Goal**: Production-ready system for demo and potential post-hackathon use.

**Deliverables**:
- End-to-end integration test suite
- Performance testing (API response time under load)
- Security audit (OWASP top 10 basics)
- Vercel frontend deployment
- FastAPI containerized deployment (Docker + cloud)
- Supabase/PostgreSQL production setup
- pgvector enabled in production
- Demo environment data hardened
- All synthetic data correctly labelled
- `docs/PROJECT_STATE.md` fully updated

**Phase Gate**: Full demo scenario runs end-to-end on production infrastructure. All labels correct.

---

## Additive Task 3 — Public Social Signal Context (PARTIAL)

This additive workstream layers opt-in, aggregate Bluesky area mentions onto
the existing itinerary map and `/api/v1/twin/social-signals` endpoint. It
does not replace MapLibre, geocoding, weather, routing, or the Phase 9
decision pipeline. Raw posts and authors stay backend-local and transient;
the map never implies post-level coordinates. The implementation has
automated coverage, but live provider access and running-server verification
remain open in this environment. See ADR-058 and `docs/PROJECT_STATE.md`.

---

## Additive Task 4 — What-if Itinerary Simulation

**Status**: Implemented locally; full automated checks and public map/API route smoke pass. Authenticated itinerary workflow verification remains pending.

This additive workstream provides bounded, read-only previews using the current itinerary and
existing weather, OSRM, social, and discovery services. Hypothetical inputs are labelled, and
alternatives reuse existing ranking. A separate explicit apply action checks the itinerary version
and delegates to the existing replanning service. Domain intelligence remains a protocol and mock
extension point; no Nugen runtime or database migration is included. Preview state is in-process,
limited to 256 entries, and expires after 15 minutes. See ADR-059.
