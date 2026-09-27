# LocaLens — Architectural Decision Records

> This file records every significant architectural decision.
> Format: Decision → Why → Alternatives Considered → Consequences
> New decisions are appended; existing decisions are never edited (only superseded).
> Last updated: 2026-09-22 (Phase 5: ADR-033 through ADR-039 added)

---

## ADR-001: Next.js App Router for Frontend

**Decision**: Use Next.js 16 with the App Router as the frontend framework.

**Why**:
- App Router is the current standard Next.js architecture (Pages Router is legacy)
- Server Components improve initial load performance
- TypeScript-first
- Strong ecosystem for PWA-oriented apps
- Excellent Vercel deployment integration

**Alternatives Considered**:
- Vite + React (SPA): Simpler setup, but no SSR; weaker for SEO and performance
- Remix: Mature, but smaller ecosystem and team familiarity
- SvelteKit: Excellent performance, but less team-common

**Consequences**:
- Server/Client component boundary must be understood by all frontend contributors
- Some third-party libraries require `"use client"` wrappers
- Deployment target is Vercel (or compatible Node/Docker environment)

---

## ADR-002: FastAPI Backend

**Decision**: Use FastAPI (Python) as the backend API framework.

**Why**:
- Native async support aligns with SQLAlchemy 2.0 async and Pydantic v2
- Auto-generated OpenAPI docs accelerate development
- Strong ecosystem for ML/AI integration (Python-native)
- Pydantic v2 provides fast, typed request/response validation

**Alternatives Considered**:
- Django REST Framework: Mature but synchronous-first; heavier for API-only use
- Node.js/Express: Would allow full-stack TypeScript; loses Python ML ecosystem
- Gin (Go): Fast, but no ML library advantage and unfamiliar to team

**Consequences**:
- Python is the primary backend language
- Must use `async def` routes and `AsyncSession` consistently
- ML/ranking code can be co-located with the API or extracted to a service

---

## ADR-003: SQLAlchemy 2.0 ORM

**Decision**: Use SQLAlchemy 2.0 (async) as the ORM layer.

**Why**:
- Stable, mature, production-grade ORM
- Full async support (`AsyncSession`, `create_async_engine`)
- Works with both SQLite (dev) and PostgreSQL (prod) without code changes
- Declarative models integrate cleanly with Pydantic

**Alternatives Considered**:
- Tortoise ORM: Async-native but smaller community; less PostgreSQL compatibility coverage
- Raw SQL (asyncpg): Maximum control; not worth the maintenance cost at this stage
- SQLModel: Thin wrapper over SQLAlchemy; acceptable, but adds abstraction layer with limited benefit

**Consequences**:
- All database interactions must use `AsyncSession`
- No SQLite-specific types or syntax in model definitions
- 2.0-style query API (`select()`, `scalars()`) must be used; 1.x `session.query()` is forbidden

---

## ADR-004: Alembic for Migrations

**Decision**: Use Alembic for database schema migrations.

**Why**:
- Official SQLAlchemy migration tool
- Autogenerate support from model definitions
- Version-controlled migration history

**Alternatives Considered**:
- Flyway: JVM-based; incompatible ecosystem
- Django migrations: Coupled to Django
- Manual schema scripts: No version control benefit

**Consequences**:
- Every schema change requires a new Alembic revision
- Existing migration files must never be edited
- Migration files committed to version control

---

## ADR-005: SQLite for Local Development

**Decision**: Use SQLite (via `aiosqlite`) for local development.

**Why**:
- Zero installation — available on all developer machines
- Instant setup; no Docker dependency for database
- Sufficient for development and functional testing
- `DATABASE_URL` switch is the only change needed for production

**Alternatives Considered**:
- Docker PostgreSQL from Day 1: More production-accurate; adds developer friction
- In-memory database: Fast; loses data on restart; impractical for iterative work

**Consequences**:
- Developers can run the full stack without Docker
- SQLite-specific behavior (case sensitivity, type affinity) must be avoided
- CI must run tests against PostgreSQL before production deployments

---

## ADR-006: PostgreSQL / Supabase for Production

**Decision**: Target PostgreSQL (Supabase managed) for the production database.

**Why**:
- pgvector extension required for semantic retrieval (Phase 6+)
- Supabase provides managed PostgreSQL with row-level security, auth, and storage
- Direct DATABASE_URL switch from SQLite; no SQLAlchemy model changes needed

**Alternatives Considered**:
- PlanetScale (MySQL): No pgvector support
- MongoDB: Document model less suited to relational marketplace data
- Firebase: No SQL; no pgvector; vendor lock-in

**Consequences**:
- pgvector is the target extension for semantic embeddings
- Phase 6+ assumes PostgreSQL in CI/staging
- Supabase managed auth may complement or replace custom JWT in a later phase (decision deferred)

---

## ADR-007: Google Gemini Ecosystem for AI

**Decision**: Use Google Gemini (text and Live API) as the primary AI provider.

**Why**:
- HackCelestial 3.0 alignment with Google ecosystem
- Gemini 2.0 Flash provides fast, capable reasoning
- Gemini Live API is the most mature real-time voice API available
- Function/tool calling supports structured application tool use
- Single provider reduces credential and integration complexity

**Alternatives Considered**:
- OpenAI GPT + Whisper: Strong but not hackathon-aligned; no native Live equivalent
- Anthropic Claude: Strong reasoning; no native Live voice API
- Multi-provider: Adds complexity without benefit at this stage

**Consequences**:
- `GEMINI_API_KEY` is a critical credential; must never reach the browser
- LLM provider is behind `AIAdapter` interface; can be swapped in future
- Gemini function calling format must be used for tool integration

---

## ADR-008: Gemini Live API for Voice

**Decision**: Use the Gemini Live API for real-time voice interaction.

**Why**:
- Core product differentiator: voice-first traveler input
- Gemini Live supports real-time audio streaming, turn detection, and tool calling
- `BidiGenerateContentConstrained` endpoint designed specifically for browser clients

**Alternatives Considered**:
- Whisper (STT) + TTS pipeline: Higher latency; not real-time; more integration work
- LiveKit + Gemini: Better network resilience (WebRTC); adds complexity for Phase 0-5
- ElevenLabs TTS: Output only; not full voice interaction

**Consequences**:
- Backend must issue ephemeral tokens via `POST /auth/live-token`
- Tokens must have short TTL and constrained scope
- WebSocket endpoint used by browser: `BidiGenerateContentConstrained`

---

## ADR-009: MapLibre / OpenStreetMap Ecosystem for Maps

**Decision**: Use MapLibre GL JS for rendering and the OSM ecosystem for data.

**Why**:
- MapLibre GL JS is open-source (no usage-based billing for renders)
- OpenStreetMap data is free, global, and community-maintained
- Nominatim for geocoding, Overpass for POI discovery, OSRM for routing — all free for reasonable usage
- No vendor lock-in; all services replaceable via adapter interface

**Alternatives Considered**:
- Google Maps: Significant per-request billing at scale; vendor lock-in
- Mapbox: MapLibre fork; billing model less favorable
- HERE Maps: Enterprise-focused; not developer-friendly for hackathon

**Consequences**:
- OSM/Nominatim rate limits apply; caching is required for production
- OSRM public instance has usage limits; self-hosted option for production
- MapTiler API key optional for premium tile styles (OSM tiles are fallback)
- All map service interactions go through adapter interfaces

---

## ADR-010: Adapter-Based External Integrations

**Decision**: All external service calls go through typed adapter interfaces, not direct API calls.

**Why**:
- Enables mock/fallback implementations for development without real credentials
- Application services depend on stable interfaces, not external API specifics
- Swapping providers (e.g., OpenWeather → Tomorrow.io) requires only adapter implementation change
- Testability: mock adapters enable unit testing without external dependencies

**Alternatives Considered**:
- Direct API calls with environment-guarded mocks: Works but couples code to API shape
- BFF (Backend for Frontend) layer: Too much overhead at this stage

**Consequences**:
- Every external service must have: (a) a typed interface, (b) a real implementation, (c) a mock/fallback
- Interface files live in `apps/api/adapters/` (Phase 1+)
- Mock adapters are used by default when API keys are absent

---

## ADR-011: Deterministic Feasibility Engine

**Decision**: The Constraint & Feasibility Engine is 100% deterministic. No LLM involvement.

**Why**:
- LLMs may hallucinate or be inconsistent about hard constraints (opening hours, budget math)
- Infeasible experience recommendations damage trust irrecoverably
- Deterministic logic is testable, predictable, and auditable
- Rejections can be expressed as machine-readable reason codes

**Alternatives Considered**:
- LLM-only feasibility: Fast to implement; not reliable; violates product trust
- LLM + deterministic validation: Redundant; LLM is still not needed for constraint checking

**Consequences**:
- Feasibility Engine is a standalone service with typed inputs and outputs
- No `if llm_says_feasible` anywhere in the codebase
- Rejection reasons are structured: `{ code, message }` pairs

---

## ADR-012: LLM Never Determines Feasibility

**Decision**: A direct corollary to ADR-011. The LLM output is never used to decide whether an experience is feasible.

**Why**: Same as ADR-011. Emphasized separately because this is an invariant that must survive code review.

**Consequences**:
- Any code that passes LLM output directly to the ranking engine without feasibility checking is a bug
- Code review must enforce this boundary

---

## ADR-013: Provider and Traveler as First-Class Domains

**Decision**: Provider and Traveler are distinct, equal first-class domains throughout the system.

**Why**:
- PS-6 explicitly requires both sides of the marketplace
- Provider intelligence is not an afterthought; it is a core product capability
- Traveler-only architectures commonly fail to deliver on two-sided marketplace requirements

**Alternatives Considered**:
- Traveler-first + minimal provider layer: Simpler short-term; fails PS-6 requirements
- Unified "user" with roles only: Loses semantic clarity

**Consequences**:
- Separate database models, API routes, and UI areas for Provider and Traveler
- Both domains are always considered in architecture discussions
- Provider experience listings belong to the Provider domain; matching belongs to shared infrastructure

---

## ADR-014: Safety Module is Architecturally Isolated

**Decision**: The Safety & Emergency Module has no dependencies on the recommendation system.

**Why**:
- Safety must remain functional even if the recommendation system fails
- Recommendation failures must never propagate to safety features
- Clean separation enables independent testing and compliance

**Consequences**:
- `apps/api/modules/safety/` must not import from `discovery`, `ranking`, `composer`, or `providers`
- Safety may only access: traveler identity, emergency configuration, external safety APIs
- Any future code review that introduces a dependency from Safety to Recommendation is a bug

---

## ADR-015: Synthetic/Demo Data Must Be Explicitly Labelled

**Decision**: All synthetic, generated, or demo data must carry an explicit `is_synthetic: true` marker.

**Why**:
- Presenting fabricated statistics as real-world facts is misleading
- Hackathon judges must be able to distinguish real data from demo data
- Prevents accidental production use of demo data

**Consequences**:
- Seed data scripts set `is_synthetic = True` on all generated records
- Provider intelligence dashboards display "Demo Data" labels when using synthetic data
- No synthetic records are presented as real without explicit user consent

---

## ADR-016: No Hardcoded Golden-Path Business Logic

**Decision**: The architecture must produce demo scenarios from general logic, not special-cased code.

**Why**:
- Golden-path demo code is fragile, unmaintainable, and not honest about system capability
- The constraint/ranking/composition logic should work for ANY valid input
- Judges can tell when a demo is hardcoded

**Alternatives Considered**:
- Hardcoded demo for hackathon speed: Faster initially; fails during questions; wrong technically

**Consequences**:
- Mumbai/Fort area seed data is acceptable as realistic demo seed data
- No `if location == "Fort"` special cases in business logic
- Demo scenarios emerge from: general seed data + general algorithms

---

## ADR-017: Overture Maps Places as the Primary Open-Data Foundation

**Decision**: Use Overture Maps Places (queried directly via DuckDB's spatial/httpfs
extensions against Overture's public cloud Parquet store) as the real-world POI
foundation for the Mumbai prototype catalog, instead of scraping any web platform.

**Why**:
- Openly licensed, bulk-queryable without an API key, with per-record source/license provenance
- No terms-of-service ambiguity, unlike scraping Google Maps/TripAdvisor/Zomato/Yelp/Instagram/etc.
- Bounding-box queries push down to Parquet row-group statistics — no full-dataset download required
- Aligns with docs/AI_CONTEXT.md INV-4 (external services behind typed interfaces) and INV-8 (provenance)

**Alternatives Considered**:
- Scraping commercial platforms: legally ambiguous, fragile, explicitly ruled out
- OpenStreetMap Overpass directly: viable but deferred to Phase 4 alongside routing/geocoding;
  Overture Places is a cleaner one-shot bulk source for the initial catalog
- Fully synthetic catalog: would not demonstrate real-world data handling, a core PS-6 expectation

**Consequences**:
- The catalog is seeded from a pinned Overture release (recorded in `data/README.md`), not a live feed
- Every Overture-derived record keeps `source_type="overture_places"`, `source_record_id`,
  `source_license`, and `source_confidence` — see ADR-018
- The Overture Places schema in the queried release has no opening-hours or rating fields;
  those remain `null`/`"unavailable"` on source-derived records rather than being invented
- Category translation from Overture's taxonomy lives in one place:
  `apps/api/src/core/category_map.py`

---

## ADR-018: Explicit Provenance Model via `ProvenanceMixin`

**Decision**: `Location`, `Provider`, and `Experience` share a `ProvenanceMixin`
(plain column mixin, not a separate joined table) carrying `source_type`,
`source_name`, `source_record_id`, `source_version`, `source_accessed_at`,
`source_url`, `source_license`, `attribution_required`, `attribution_text`,
`source_confidence`, `is_synthetic`, and `is_enriched`.

**Why**:
- A direct corollary of ADR-015 (synthetic data must be labelled) extended to real
  open-data provenance: source facts, LocaLens enrichment, and synthetic demo content
  must never be visually or structurally indistinguishable
- A mixin keeps querying simple (no joins needed to know a record's origin) while still
  avoiding copy-pasted column definitions across the three entities that need it

**Alternatives Considered**:
- Separate normalized `Source` table with a polymorphic FK: more "correct" relationally,
  but adds join complexity for very little benefit at this dataset size (~350 experiences)
- No provenance tracking, trust the seed script: fails the "never confuse source facts with
  LocaLens enrichment" requirement and cannot survive re-ingestion against a newer release

**Consequences**:
- The Experience API (`schemas/experience.py`) surfaces `source_type`, `source_license`,
  `attribution_required`/`attribution_text`, `is_synthetic`, and `is_enriched` so the frontend
  (and any future consumer) can render honest status badges instead of presenting everything
  as uniformly "verified"
- `Experience` has a unique constraint on `(source_type, source_record_id)` to prevent
  duplicate ingestion of the same upstream record

---

## ADR-019: JWT Access Token (Memory) + HttpOnly Refresh Cookie

**Decision**: Authentication issues two JWTs — a short-lived access token (~15 min,
HS256, `JWT_ACCESS_SECRET`) returned in the JSON response body and held by the
frontend only in memory (`lib/auth/tokenStore.ts`, never localStorage/
sessionStorage/IndexedDB) — and a longer-lived refresh token (~7 days, HS256,
a **separate** `JWT_REFRESH_SECRET`) set only as an HttpOnly, SameSite=Lax
cookie (`__Host-` prefixed when Secure — see ADR-020), never present in any
JSON response.

**Why**:
- A token in `localStorage`/`sessionStorage` is readable by any script on the
  page — one XSS bug anywhere leaks every session indefinitely. In-memory
  storage is wiped on tab close/reload by construction.
- An HttpOnly cookie is invisible to JavaScript entirely, so even a
  successful XSS cannot read the refresh token directly (it can still ride
  the cookie for same-origin requests, which is why CSRF-relevant
  SameSite=Lax and a tightly scoped auth surface matter — see ADR-020).
- Distinct signing secrets mean a leaked access-token secret cannot be used
  to forge a refresh token and vice versa.
- FastAPI (not Next.js/NextAuth/Better Auth) is the single authentication
  authority end to end — no second auth platform, per docs/AI_CONTEXT.md.

**Alternatives Considered**:
- Both tokens as HttpOnly cookies: simpler frontend code, but then every
  API call needs cookie-based auth and CSRF protection becomes mandatory
  everywhere, not just on the auth surface — more attack surface for a
  prototype timeline
- Both tokens in localStorage: rejected outright — the standard XSS-token-
  theft failure mode explicitly ruled out by the phase requirements
- Session cookies only (opaque, server-side session store): viable, but
  loses the stateless-access-token benefit (no DB round trip to authorize
  most requests) without buying much extra safety over the chosen design

**Consequences**:
- `lib/api/client.ts` attaches `Authorization: Bearer <token>` from the
  in-memory store and sends `credentials: "include"` so the refresh cookie
  travels automatically; a 401 on any non-auth endpoint triggers exactly one
  shared refresh-and-retry (never an unbounded loop)
- A page reload always starts signed-out until `AuthProvider`'s bootstrap
  effect calls `/auth/refresh`; this is expected, not a bug
- Reading the refresh cookie server-side (`request.cookies`) is the only
  way to obtain it — `apps/web/proxy.ts` checks only for its *presence*
  (never decodes it) for an optimistic redirect; it is not the authorization
  boundary

---

## ADR-020: Refresh Token Rotation with Reuse Detection, Stored as a Hash

**Decision**: Every `/auth/refresh` call revokes the current `AuthSession`
row and issues a brand-new refresh token backed by a new row
(`replaced_by_session_id` links them). The database never stores the raw
refresh token — only `sha256(token)` in `token_hash` — so a database read
alone can't be replayed as a valid session. Reuse of an already-rotated or
revoked refresh token revokes **every** active session for that user rather
than just rejecting the one request.

**Why**:
- Rotation limits the blast radius of a stolen refresh token to a single
  use before it's invalidated
- Reuse of a rotated token is the textbook signal of a stolen/replayed
  token (the legitimate client already moved to the new one) — treating it
  as "log everyone out" is the standard mitigation (OAuth 2.0 refresh token
  rotation reuse detection) rather than quietly minting another session for
  whoever replayed it
- Hashing at rest means a database dump doesn't hand over live sessions

**Alternatives Considered**:
- No rotation (static long-lived refresh token): simpler, but a single
  leaked token stays valid for its entire 7-day lifetime
- Rotation without reuse detection: still leaves a window where a stolen
  token and the legitimate one race, with no signal to the server
- Storing the raw refresh token encrypted rather than hashed: adds a
  decryption key management problem for no benefit, since the server never
  needs to recover the original token — only to compare hashes

**Consequences**:
- `AuthSession` (`src/models/auth_session.py`) is the source of truth for
  "is this refresh token still good" — JWT signature validity alone is not
  sufficient, since a valid-looking rotated token must still be rejected
- `scripts/seed.py`'s Overture/synthetic reseed never touches this table
  (or `users`/`travelers`) — see ADR-021

---

## ADR-021: Provider Ownership — Catalog vs. Registered, Server-Derived Only

**Decision**: `provider_id`/ownership is **never** accepted from a request
body on any experience or availability mutation — it is always derived
from the authenticated `Provider` row loaded via
`get_current_provider` (`src/core/deps.py`). Three distinct provider
lineages coexist and are never blurred:
1. **Catalog-imported** (`source_type="overture_places"`): no `user_id`,
   `verification_status="catalog_imported"` — real-world businesses from
   open data, not LocaLens accounts.
2. **Synthetic demo** (`source_type="synthetic"`): no `user_id`,
   fictional, `is_synthetic=true`.
3. **Registered** (`source_type="registered"`, experiences
   `source_type="provider_submitted"`): created through
   `POST /api/v1/auth/register`, `user_id` set, owned end to end by an
   authenticated account.

Provider.user_id was already nullable from Phase 2 (built in anticipation
of this split) — no migration was needed to loosen it.

**Why**:
- PS-6 explicitly requires providers to manage only their own listings;
  trusting a client-supplied `provider_id` would let any authenticated
  provider claim or edit anyone else's data
- Hundreds of imported/synthetic providers have no real person behind
  them — inventing login credentials for all of them would be dishonest
  demo data and a maintenance trap (see docs/AI_CONTEXT.md INV-8/INV-9)
- Provider claiming (letting a real business "claim" its catalog-imported
  record) is a deliberately separate, later feature — mixing it in here
  would blur the ownership model this ADR exists to keep clean

**Consequences**:
- `ExperienceCreateRequest`/`ExperienceUpdateRequest` have no
  `provider_id` field at all — it cannot be supplied even accidentally
- Ownership checks return 404 (not 403) for another provider's resource,
  matching docs' "don't disclose that it exists" guidance
  (`_get_owned_or_404` in `src/api/v1/experiences.py` /
  `src/api/v1/availability.py`)
- `scripts/seed.py`'s `reset_tables()` deletes only rows with
  `source_type in ("overture_places", "synthetic")` — registered
  providers/experiences and shared `ExperienceCategory` rows (upserted by
  slug, stable IDs) survive every reseed. This was a real bug caught
  during Phase 3 testing: the original Phase 2 script wiped and
  regenerated *all* providers/categories with fresh UUIDs on every run,
  which would have deleted real accounts' data and orphaned their
  `category_id` foreign keys on reseed.

---

## ADR-022: Portable Haversine + Bounding-Box Radius Search (No PostGIS/Spatial Extension)

**Decision**: Radius-based discovery uses a plain-Python Haversine
distance calculation (`apps/api/src/core/geo.py`) plus a SQL bounding-box
pre-filter (`min_lat/max_lat/min_lng/max_lng` computed from the radius),
rather than PostGIS, SpatiaLite, or any database spatial extension.

**Why**:
- ADR-005/ADR-006 commit to SQLite in dev and PostgreSQL in production —
  a spatial extension would need to exist and behave identically on both,
  which SQLite does not guarantee out of the box
- Discovery radii here are small (a city-scale prototype, capped by
  `DISCOVERY_MAX_RADIUS_KM`), so the accuracy loss vs. a true geodesic/
  PostGIS calculation is negligible at this scale
- Keeps the query portable: the bounding box does the cheap SQL-level
  filtering (uses ordinary indexed lat/lng columns), and the more
  expensive/precise Haversine distance runs only over that already-small
  candidate set in Python

**Alternatives Considered**:
- PostGIS `ST_DWithin`: accurate and fast at scale, but ties the schema to
  PostgreSQL and reintroduces the SQLite-dev-parity problem ADR-005 exists
  to avoid
- Bounding box only, no Haversine refinement: cheaper, but a bounding box
  is not a circle — corners would incorrectly pass filtering

**Consequences**:
- `ExperienceRepository.search()` never sorts or paginates by distance in
  SQL — it fetches a bounded candidate set (`DISCOVERY_CANDIDATE_CAP`) and
  `ExperienceDiscoveryService` does distance sort/pagination in Python
- Distance figures are always labelled straight-line (Haversine), never
  confused with road distance from OSRM (see ADR-024)

---

## ADR-023: Nominatim as the Geocoding Adapter, Explicit-Submit Only

**Decision**: `NominatimGeocodingAdapter` (`apps/api/src/adapters/geocoding.py`)
wraps the public Nominatim API for forward/reverse geocoding. The frontend
never calls Nominatim directly, and search is explicit-submit only — no
autocomplete/type-ahead query-per-keystroke behavior anywhere
(`apps/web/hooks/useLocationSearch.ts`).

**Why**:
- Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/)
  explicitly prohibits autocomplete-style rapid-fire querying and requires
  a descriptive User-Agent and a max ~1 req/sec
- Routing all calls through the backend adapter (never browser → Nominatim
  directly) keeps rate limiting, caching, and the required User-Agent
  centralized in one place rather than duplicated/unenforceable in client JS
- Aligns with ADR-010 (adapter-based external integrations) and
  docs/AI_CONTEXT.md's external-services-behind-typed-interfaces invariant

**Alternatives Considered**:
- Browser calls Nominatim directly: simpler, but violates the usage policy
  (no server-side rate limiting/caching possible) and exposes a third-party
  dependency directly to end users
- A commercial geocoder (Google/Mapbox geocoding): billed, and ADR-009
  already rules out vendor-billed map services for this project

**Consequences**:
- `IntervalRateLimiter` (`NOMINATIM_MIN_INTERVAL_SECONDS`) and `TTLCache`
  (`NOMINATIM_CACHE_TTL_SECONDS`) are mandatory on every Nominatim call
- `NOMINATIM_USER_AGENT` must be a real descriptive string, never a
  browser-style UA
- If Nominatim is slow/unavailable, `AdapterTimeoutError`/
  `AdapterUnavailableError` propagate as an empty-results UI state, never
  a crashed discovery page

---

## ADR-024: OSRM for Routing, with Honest Haversine Fallback Labelling

**Decision**: `OSRMRoutingAdapter` (`apps/api/src/adapters/routing.py`) calls
the public OSRM demo server for road-network `route` and `table` (travel-time
matrix) results. Every travel-time/distance figure returned to the frontend
carries an explicit `source: "osrm" | "haversine_estimate"` field — the two
are never conflated or silently substituted for each other without labelling.

**Why**:
- OSRM gives real road-network routing (turns, one-ways, actual travel
  time), which a straight-line Haversine estimate cannot
- The public OSRM demo instance has no uptime SLA — a hackathon prototype
  cannot assume it's always reachable, so a fallback is required for the
  catalog to keep working
- Presenting an estimated distance as if it were a real route violates the
  project's provenance-honesty principle (ADR-018, docs/AI_CONTEXT.md INV-8)

**Alternatives Considered**:
- OSRM only, no fallback: simpler, but a single external outage would take
  down travel-time display (and, if not carefully isolated, discovery
  itself) entirely
- Self-hosted OSRM: more reliable, out of scope for a hackathon timeline;
  noted in `docs/PROJECT_STATE.md` Known Risks as a production follow-up

**Consequences**:
- `GET /experiences` enriches only the current page's results (capped at
  `OSRM_MAX_MATRIX_DESTINATIONS`) via the table/matrix endpoint, not every
  candidate — keeps a single request bounded
- `ExperienceDetail.tsx`'s "Show route" explicitly renders
  `(estimated — routing unavailable)` when `source === "haversine_estimate"`
- Profile is restricted to `OSRM_ALLOWED_PROFILES` (`driving`/`walking`/
  `cycling`); an unsupported profile is rejected before the HTTP call

---

## ADR-025: Overpass for Nearby-POI Discovery — Informational, Never Catalog Data

**Decision**: `OverpassPOIAdapter` (`apps/api/src/adapters/poi.py`) queries
the public Overpass API using deterministic, server-built Overpass QL from a
fixed category allowlist (`POI_CATEGORY_TAGS`) — never free-form or
user-supplied QL. Overpass results are surfaced only as transient map
annotations; they are never written to the database and never become
`Experience` catalog rows.

**Why**:
- Overpass QL is a full query language; accepting any user-influenced QL
  string would be a request-forgery/DoS risk against a shared public
  service and a QL-injection-style bug class
- A POI (e.g. "there is a museum here") is not the same claim as a LocaLens
  "experience" (bookable, curated, with pricing/availability/provenance) —
  conflating the two would misrepresent unverified OSM tag data as curated
  marketplace listings, directly contradicting ADR-017/ADR-018's provenance
  discipline
- Overpass's public instance fair-use policy load-sheds heavily
  (429/504) under pressure, so treating it as informational-only, best-effort
  keeps this from being a load-bearing dependency for core discovery

**Alternatives Considered**:
- Auto-import Overpass POIs into the catalog: rejected outright — no
  pricing, no curation, no booking semantics, and explicitly forbidden by
  the phase's scope boundary (OSM POIs are not LocaLens experiences)
- Allow arbitrary Overpass QL from the client: rejected as a security/
  abuse risk against a shared public API

**Consequences**:
- `_build_overpass_query()` is the only place Overpass QL is constructed;
  it accepts a category (validated against the allowlist), center point,
  and radius (capped at `OVERPASS_MAX_RADIUS_M`) — nothing else
- A 429/504 from Overpass surfaces as `AdapterRateLimitedError`/
  `AdapterUnavailableError`, and the map/location UI simply shows no nearby
  POIs rather than failing the page
- `data/README.md` §9.2 documents this distinction explicitly for anyone
  extending the pipeline later

---

## ADR-026: MapLibre GL JS + OpenFreeMap as the Map Rendering Stack

**Decision**: `apps/web/components/common/MapSurface.tsx` renders the map
using MapLibre GL JS (open-source, no billing) with OpenFreeMap
(`tiles.openfreemap.org/styles/liberty`, no API key) as the default style/
tile provider, configurable via `NEXT_PUBLIC_MAP_STYLE_URL`. This replaces
the Phase 1 static placeholder.

**Why**:
- ADR-009 already committed to MapLibre + the OSM ecosystem over Google
  Maps/Mapbox specifically to avoid per-request billing and vendor lock-in
- OpenFreeMap requires no API key and is a maintained, production-usable
  vector tile host built on OSM data — no MapTiler key needed to get a
  working map in this project (MapTiler remains an optional override)
- A configurable style URL means swapping tile providers later is a single
  environment variable change, not a code change

**Alternatives Considered**:
- MapTiler-hosted styles: viable, but requires an API key that shouldn't be
  a hard requirement for running the project locally
- Raw OSM raster tile server: usage policy explicitly discourages
  programmatic/app embedding without a dedicated agreement

**Consequences**:
- `lib/config/map.ts` is the single source of truth for style URL, default
  center/zoom, and attribution HTML — never hardcoded inline in a component
- MapLibre's `AttributionControl` always renders the required OSM/
  OpenFreeMap attribution on-map (compact mode), never removed
- If map initialization throws (e.g. style fetch fails), `MapSurface`
  renders a graceful fallback panel rather than a blank/broken map, and the
  experience list beside it keeps working independently

---

## ADR-027: Clustered GeoJSON Source Instead of Per-Result DOM Markers

**Decision**: Discovery results are rendered as a single clustered GeoJSON
source (`experiences`, MapLibre's built-in `cluster: true`) with circle/
symbol layers, not one DOM marker (`new Marker()`) per result.

**Why**:
- DOM markers don't scale — hundreds of results would mean hundreds of
  DOM nodes reflowing on every pan/zoom, a known MapLibre/Mapbox
  performance pitfall
- GeoJSON-source clustering is GPU-rendered and handles zoom-dependent
  aggregation (cluster counts) for free, giving a materially better UX at
  the catalog's current and future scale (350+ experiences)

**Alternatives Considered**:
- One DOM marker per experience: simplest to reason about, rejected for
  the scaling reason above
- Third-party clustering library (Supercluster) wired to DOM markers:
  redundant — MapLibre's native GeoJSON clustering already provides this

**Consequences**:
- Selection state is encoded in feature `properties.selected` (set when
  building the `FeatureCollection`) rather than tracked as a separate
  per-marker prop — see `lib/geo/geojson.ts`
- Clicking a cluster zooms to its expansion zoom rather than immediately
  fanning out individual markers

---

## ADR-028: "Search This Area" — Map Panning Never Auto-Triggers a Query

**Decision**: Panning or zooming the map never automatically re-queries the
API. Instead, `MapSurface` shows a floating "Search this area" button after
`dragend`/`zoomend`, and only an explicit click re-runs discovery against the
new bounds (`onSearchThisArea` in `DiscoverExperience.tsx`).

**Why**:
- Auto-querying on every pan/zoom would multiply API (and downstream OSRM
  travel-time enrichment) calls dramatically during normal map exploration,
  directly working against the rate-limiting/caching discipline the other
  Phase 4 ADRs establish
- Google Maps-style "Search this area" is a well-understood UX pattern that
  gives users control rather than surprising them with results silently
  changing underfoot

**Alternatives Considered**:
- Debounced auto-query on `moveend`: still multiplies calls under normal
  browsing and can feel like the list is changing unpredictably
- No location-based re-query at all: worse UX, defeats the purpose of a
  map/list-synced discovery view

**Consequences**:
- `handleSearchThisArea` in `DiscoverExperience.tsx` computes a center +
  radius from the current map bounds and merges it into the URL-synced
  discovery state, so the resulting search is shareable like any other
  discovery URL
- The button only appears when `onSearchThisArea` is actually wired up
  (the detail-page map, which has no list to resync, never shows it)

---

## ADR-029: URL-Synchronized Discovery State

**Decision**: All discovery filters (`q`, `category`, `lat`, `lng`,
`radius_km`, `budget`, `duration`, `sort`) are encoded into the `/discover`
URL query string (`apps/web/lib/discovery/urlState.ts`) and read back out on
load, via `router.replace` (no full navigation, no added history entries per
keystroke/filter change).

**Why**:
- A shareable/bookmarkable discovery URL is a basic expectation for a
  search-style page — "here's what I found" should be a link, not a
  screenshot
- Keeping the URL as the source of truth (rather than only component state)
  means a page refresh reproduces the same results deterministically

**Alternatives Considered**:
- Component state only, no URL sync: simpler, but loses shareability and
  refresh-reproducibility
- Full navigation per filter change: correct but causes visible page
  reloads/flicker for what should feel like an instant filter

**Consequences**:
- `discoveryStateToParams`/`parseDiscoveryStateFromParams` are the single
  encode/decode pair — no ad hoc query-string handling elsewhere
- `router.replace(..., { scroll: false })` is used specifically so
  changing a filter never yanks scroll position or pushes a new history
  entry per keystroke

---

## ADR-030: External-Service Resilience — TTL Cache + Interval Rate Limiter per Adapter

**Decision**: Every external adapter (Nominatim, Overpass, OSRM) gets its
own `TTLCache[T]` (`apps/api/src/core/cache.py`) and `IntervalRateLimiter`
(`apps/api/src/core/rate_limit.py`) instance, independently configured via
`.env` (`*_CACHE_TTL_SECONDS`, `*_MIN_INTERVAL_SECONDS`), rather than one
shared global cache/limiter.

**Why**:
- The three services have very different fair-use characteristics
  (Nominatim ~1/sec, Overpass more restrictive and load-shedding, OSRM demo
  best-effort) — a single shared limiter would either be too conservative
  for some or too aggressive for others
- Per-adapter TTLs matter differently too: a geocoded place rarely changes
  (long TTL is fine), while POI/route results are more scenario-specific

**Alternatives Considered**:
- A single shared rate limiter/cache for "external calls" generically:
  simpler to wire up, but forces one-size-fits-all tuning across services
  with materially different usage policies
- No caching at all: simplest, but wastes fair-use quota on repeat lookups
  within a single user session (e.g. re-rendering the same map view)

**Consequences**:
- `IntervalRateLimiter.wait()` uses an `asyncio.Lock` so concurrent
  requests from multiple users queue rather than burst past the configured
  interval
- Cache keys are built from the normalized request parameters (query
  string, coordinates, category, radius) so distinct queries never
  collide, but identical repeat queries within the TTL window are free

---

## ADR-031: `LOCATION_SERVICES_ENABLED` Kill Switch with Mock Adapter Fallback

**Decision**: `apps/api/src/core/location.py`'s dependency providers
(`get_geocoding_adapter`/`get_routing_adapter`/`get_poi_adapter`) switch to
the existing `Mock*Adapter` implementations whenever
`LOCATION_SERVICES_ENABLED=false`, and the experience catalog (`GET
/experiences` with lat/lng/radius) is designed to keep returning real
database results either way — travel-time enrichment is additive, never a
precondition for discovery to work.

**Why**:
- A hackathon demo room may have unreliable or filtered internet access —
  the core catalog experience must not depend on three public third-party
  services staying up during a live demo
- This is also a genuine local-dev/CI convenience: tests and offline work
  don't need network access to exercise the catalog

**Alternatives Considered**:
- No kill switch, always call real services: simplest, but makes the whole
  app fragile to any one of three external dependencies
- Fail loudly instead of falling back: technically honest but a worse
  product experience than degrading gracefully with clear (if reduced)
  functionality

**Consequences**:
- All Phase 4 backend tests inject `Mock*Adapter`s via
  `app.dependency_overrides` (see `apps/api/tests/conftest.py`) rather than
  hitting the network — this is also what makes the test suite deterministic
  and fast
- Manually verified: with `LOCATION_SERVICES_ENABLED=false`, `GET
  /experiences?lat=...&lng=...&radius_km=...` still returned 200 with real
  DB matches, while `GET /location/search` gracefully returned
  `{"items": []}` instead of erroring

---

## ADR-032: Location Data Is Client-Provided and Ephemeral — No Server-Side Location Storage

**Decision**: The user's own coordinate (from `navigator.geolocation` via
`useUserLocation`, or from an explicit Nominatim search) is never persisted
server-side. It exists only in frontend component state and as `lat`/`lng`
query parameters on outgoing API requests — there is no `user_location`
table, no location history, no server-side tracking of where a user has
searched from.

**Why**:
- Precise personal location is sensitive data; storing it creates privacy
  obligations and breach risk with no product requirement driving the need
  to retain it — Phase 4's scope is "use my current search radius," not
  location history/tracking
- `useUserLocation`/`useLocationSearch` are explicit-trigger only (the user
  clicks "use my location" or submits a search) — geolocation is never
  requested automatically on page load, so there's no passive location
  collection either

**Alternatives Considered**:
- Store recent search locations per user for convenience ("recent
  searches"): a reasonable future feature, but out of scope for Phase 4 and
  deliberately not added preemptively (see docs/AI_CONTEXT.md's
  no-speculative-scope principle)

**Consequences**:
- A user's location is only as persistent as the current browser tab/URL —
  refreshing without a `lat`/`lng` in the URL returns to no location set
  (the "Search this area" flow does put the derived center into the URL,
  which is the intended shareability behavior from ADR-029, not location
  tracking)
- No new database migration was needed for Phase 4's location features

---

## ADR-033: `TravelerContext` as the Single Structured-Intent Schema for Text and Voice

**Decision**: Both the text conversational path and the Gemini Live voice
path produce/consume the same `TravelerContext` Pydantic schema
(`apps/api/src/schemas/conversation.py`) and its mirrored TypeScript type
(`apps/web/types/conversation.ts`). There is no separate "voice context"
model. The schema is deliberately scoped to what Phase 5 needs
(understanding + retrieval) — no itinerary/feasibility fields, per
docs/AI_CONTEXT.md's no-speculative-scope principle.

**Why**:
- The two modalities are the same product capability with different
  transport — maintaining two parallel schemas would let them drift and
  produce inconsistent discovery behavior for the same spoken vs. typed
  request
- A shared schema is what makes text/voice parity (the same request
  through either modality should produce materially equivalent discovery
  parameters) enforceable rather than aspirational
- Gemini never supplies coordinates in either path — `location_text` is
  free text only (e.g. "Fort, Mumbai"), resolved through the existing
  Phase 4 `GeocodingAdapter` only on an explicit user action (see ADR-023),
  never invented or auto-applied by the model

**Alternatives Considered**:
- Separate `TextTravelerContext`/`VoiceTravelerContext` schemas: would let
  each modality specialize, but voice's actual "context" is really just
  the `search_experiences` tool call's arguments (Gemini Live drives the
  tool directly rather than producing an intermediate context object) —
  introducing a parallel schema just to force symmetry would be artificial
- Free-form/untyped context (a `dict`): rejected outright — every other
  AI-adjacent boundary in this codebase (discovery filters, adapter
  results) is strictly typed; an untyped context would be the one
  exception and a likely source of silent bugs

**Consequences**:
- `apps/web/lib/discovery/travelerContextToPatch.ts` has two sibling
  functions — `travelerContextToDiscoveryPatch` (text path, from a real
  `TravelerContext`) and `searchArgsToDiscoveryPatch` (voice path, from
  the tool call's own `SearchExperiencesArgs`) — both producing the same
  `Partial<DiscoveryState>` shape, so downstream UI code never needs to
  know which modality produced a given patch
- Any future Phase 6+ field (e.g. resolved feasibility) is added to this
  one schema, not duplicated across two

---

## ADR-034: One Gemini Call Per Text Turn — Extraction Only, Deterministic Template Reply

**Decision**: A text conversational turn makes exactly one Gemini call:
structured `TravelerContext` extraction (`generate_content` with
`response_schema=TravelerContext`). The assistant-facing reply text is
built from a deterministic string template
(`apps/api/src/services/conversation.py::_build_assistant_text`), never a
second free-form Gemini call narrating the results.

**Why**:
- A second "narrate the results" call is a second surface where the model
  could stray into claims the application hasn't verified — "these are
  all open now," "this fits your budget perfectly" — directly violating
  the discovery-is-not-feasibility boundary (Phase 6 owns feasibility)
- Halving the Gemini calls per turn halves latency and quota cost for a
  hackathon-timeline prototype, with no loss of the core capability
  (understanding + retrieval)
- A deterministic template is trivially reproducible in `MockAIAdapter`
  mode — text discovery behaves identically in shape whether or not
  Gemini is configured, differing only in the quality of interest
  extraction, not in whether a coherent reply exists at all

**Alternatives Considered**:
- A second Gemini call for natural-language result narration: more
  conversational-feeling prose, but doubles cost/latency and reopens the
  fabrication-risk surface this ADR exists to close. Deferred — if a
  future phase adds this, it must explicitly forbid feasibility-adjacent
  claims in the narration prompt, mirroring the Live system instruction's
  constraints (ADR-036)
- Returning raw structured data with no assistant text at all: less
  useful for a conversational product; the template gives a legible
  one-line summary ("Found N experiences matching X near Y") without the
  cost/risk of free-form generation

**Consequences**:
- `handle_text_turn` (`src/services/conversation.py`) is the only place
  this template lives — voice turns don't need an assistant_text field at
  all, since Gemini Live itself generates the spoken response (governed
  by the system instruction, see ADR-036), using the real tool result it
  already received
- If Phase 6+ adds real feasibility data, the template can incorporate it
  as a verified fact, but the template itself must never claim feasibility
  it wasn't given

---

## ADR-035: Ephemeral Gemini Live Tokens with Server-Locked `live_connect_constraints`

**Decision**: `POST /api/v1/auth/live-token` (traveler-only,
`require_traveler`) calls `client.auth_tokens.create(...)` and returns a
short-lived ephemeral token to the browser. The token's
`live_connect_constraints` locks it to `gemini_model_live`, the
`search_experiences` tool declaration, response modality, and
transcription config — `lock_additional_fields` prevents the browser from
overriding these. `GEMINI_API_KEY` never leaves the backend process; the
issued token is never logged or persisted server-side.

**Why**:
- A master API key in browser code/bundles is a standing secret-exposure
  risk the moment the app ships anywhere public — hackathon demo or not
- Locking the token's configuration server-side (not just documenting "the
  browser should only use these settings") means a compromised or
  tampered browser client cannot redefine the tool set or inject a
  different system prompt even if it tries — the security boundary is
  enforced by Google's own token verification, not just application
  discipline
- Short TTLs (`GEMINI_LIVE_TOKEN_TTL_SECONDS=60` to start a session,
  `GEMINI_LIVE_SESSION_TTL_SECONDS=1800` once connected — Google's own
  documented defaults) bound the blast radius of a leaked token to a
  single short-lived session

**Alternatives Considered**:
- Proxying the entire Live WebSocket through the FastAPI backend: keeps
  the master key fully server-side with no ephemeral-token mechanism at
  all, but adds a full-duplex audio-proxying layer to the backend for no
  real security benefit over the officially-supported ephemeral-token
  pattern, and reintroduces latency for a real-time audio product
- No configuration locking (unlocked ephemeral token): simpler token
  issuance, but leaves tool/model tampering possible from a compromised
  client — rejected given INV-15/INV-16 (docs/AI_CONTEXT.md)

**Consequences**:
- `apps/api/src/adapters/ai.py::GeminiAIAdapter.issue_live_token` is the
  only place a Live token is minted; `apps/web/lib/voice/geminiLiveClient.ts`
  holds it only in memory (never localStorage/sessionStorage/cookies) for
  the lifetime of one voice session
- Verified in tests (`tests/test_live_token_api.py`): unauthenticated →
  401; provider-role account → 403; `MockAIAdapter` (Gemini disabled) →
  503, never a faked success
- Manual verification with a real `GEMINI_API_KEY` (browser DevTools
  inspection confirming the key never appears in network/storage/bundle)
  is a required step before claiming the voice path demo-ready — see
  docs/PROJECT_STATE.md's Partial section

---

## ADR-036: Backend-Only Tool Execution — `search_experiences` Is the Only Gemini Tool

**Decision**: Exactly one Gemini tool is registered this phase:
`search_experiences` (`apps/api/src/services/ai_tools.py`). The Live
system instruction and the ephemeral token's `live_connect_constraints`
both declare only this tool. When Gemini Live emits a `tool_call`, the
browser's only responsibility is to forward it verbatim to
`POST /api/v1/conversations/{id}/tool-calls` and relay the real response
back via `session.sendToolResponse(...)` — it contains no discovery logic
of its own (`apps/web/lib/voice/geminiLiveClient.ts::handleToolCalls`).
The backend route rejects any tool name other than `search_experiences`
with a 422, and validates `args` as `SearchExperiencesArgs` (strict
Pydantic, `extra="forbid"`) before ever touching the discovery service —
raw model tool arguments are never trusted directly.

**Why**:
- "The browser is a transport/UI layer, not a business-logic executor" is
  a hard product/security requirement (docs/AI_CONTEXT.md INV-3, INV-15) —
  putting `ExperienceDiscoveryService` logic in the browser would both
  duplicate the Phase 4 discovery engine and remove the server-side
  validation boundary entirely
- An allowlist of exactly one tool name, checked server-side, is the
  simplest possible defense against a manipulated or buggy Live session
  attempting to invoke application behavior that doesn't exist yet
  (booking, feasibility, provider data) — those tools are explicitly not
  implemented and must stay that way until their owning phase
- Reusing `ExperienceRepository`/`ExperienceDiscoveryService` directly
  (`execute_search_experiences` is a thin wrapper, not a second
  algorithm) keeps discovery behavior identical across the `GET
  /experiences` REST path, the text conversational path, and the voice
  tool-call path — one deterministic discovery engine, three entry points

**Alternatives Considered**:
- Executing the tool call fully client-side against a public
  read-only discovery endpoint: would avoid a round trip to
  `/tool-calls`, but reintroduces business logic into the browser and
  loses the opportunity to persist tool-call metadata into the
  conversation transcript
- A generic "execute any registered backend function" bridge: more
  reusable for future tools, but overkill for exactly one tool this
  phase; a small explicit `if payload.name != "search_experiences"` check
  is more auditable than a generic dispatcher today. Revisit if/when
  Phase 6+ needs `check_feasibility` as a second tool.

**Consequences**:
- `SEARCH_EXPERIENCES_DECLARATION` (`src/services/ai_tools.py`) is the
  single source of truth for the tool's schema, imported by both the
  adapter (for `live_connect_constraints` locking) and implicitly relied
  upon by the route's `SearchExperiencesArgs` validation — they cannot
  silently drift apart
- Tool results are capped (`limit` 1–10, default 5) and marked `truncated`
  when more results exist — never dumping the full catalog into the Live
  context (docs/AI_CONTEXT.md's bounded-context principle)
- Every `search_experiences` tool call — text or voice — persists an
  assistant-role `ConversationMessage` with `tool_call_metadata` (tool
  name, args, result count only — never raw internals), so both
  modalities share one durable transcript

---

## ADR-037: Gemini Live System Instruction Forbids Feasibility Claims and Fabrication

**Decision**: The Live session's system instruction (embedded in the
`live_connect_constraints` config locked into the ephemeral token)
explicitly forbids Gemini from inventing experience names, prices,
durations, ratings, opening hours, availability, or travel times, from
claiming a candidate is feasible/bookable, or from pretending a
booking/reservation exists. It may ask concise clarification questions
and call `search_experiences`, but the LLM is never the feasibility
authority (a direct corollary of ADR-011/ADR-012, extended to the voice
modality).

**Why**:
- Voice is a lower-friction, higher-trust-feeling interaction than a web
  form — a spoken confident claim ("yes, this is open now and fits your
  budget") is more likely to be taken at face value by a user than the
  same unfounded claim in text, making the fabrication risk here higher
  stakes, not lower
- The system instruction is the correct enforcement layer at the model's
  own boundary — it constrains what the model *says*, complementing (not
  replacing) the separate constraint that the model can never trigger
  unverified application behavior (ADR-036)

**Alternatives Considered**:
- Rely solely on backend tool-result data being accurate and trust the
  model to only repeat it: insufficient — an LLM given accurate retrieved
  facts can still add unfounded interpretive claims ("this should work
  great for you") unless explicitly told not to
- Post-hoc filtering of Gemini's spoken output for forbidden claims: not
  feasible for real-time audio (no text to filter before it's already
  spoken) and adds complexity for marginal benefit over prompting

**Consequences**:
- The same constraints apply to the text path's deterministic template
  (ADR-034) by construction, since it only ever states facts the
  application itself computed
- A future Phase 6 feasibility engine, once it exists, can be explicitly
  *allowed* into the system instruction as a new verified-fact source —
  until then, "feasible" is a word the assistant is instructed not to use

---

## ADR-038: Conversation Persistence — Normalized Messages + a Denormalized Context Snapshot

**Decision**: `ConversationMessage` rows are a normalized, append-only
transcript (one row per turn, `role`/`text`/`tool_call_metadata`).
`ConversationSession.latest_traveler_context` is a single denormalized
JSON snapshot of the most recently extracted `TravelerContext` — not a
history table. Audio is never persisted in either place; `text` holds
transcript text only (Gemini's `input_transcription`/`output_transcription`
for voice, the raw typed message for text).

**Why**:
- The transcript is genuinely a growing ordered list that needs to be
  paginated/bounded (`CONVERSATION_HISTORY_WINDOW`) and queried by
  role/time — a normalized table is the natural fit, consistent with how
  `AuthSession` and other append-style entities are modeled
- The current structured context is a single mutable value with no
  independent lifecycle from its owning session — a JSON column avoids a
  migration for every `TravelerContext` field change, following the same
  precedent as `Traveler.preferences`/`Experience.tags` (plain JSON
  columns, portable across SQLite/PostgreSQL)
- Keeping the JSON value to a single snapshot (not an array of historical
  contexts) directly satisfies the bounded-context requirement — there is
  no unbounded-growth risk in the JSON column itself, only in the
  message table, which is naturally boundable by query

**Alternatives Considered**:
- A normalized `TravelerContext` history table: more queryable per-turn
  context evolution, but adds a table and a migration surface for a value
  that, for this phase's needs, only ever needs to be "the latest one" —
  deferred until a real use case (e.g. Phase 9 replanning) needs it
- Storing the full conversation as one big JSON blob on the session: would
  need manual truncation logic to stay bounded and creates read-modify-
  write races under concurrent voice+text turns on the same session —
  rejected in favor of normalized rows

**Consequences**:
- `GET /api/v1/conversations/{id}` returns the full message list for now
  (small dataset at hackathon scale); if the transcript grows large in a
  future phase, pagination can be added without a schema change
- New Alembic migration (`conversation sessions and messages`) verified
  against both a fresh database and the existing seeded database — no
  data loss, 353 experiences/311 providers unaffected

---

## ADR-039: Frontend Testing — Vitest Introduced, Scoped to Pure High-Risk Logic Only

**Decision**: Phase 5 introduces Vitest as the frontend's first test
framework (none existed through Phase 4), scoped narrowly to pure,
deterministic, high-risk logic: the AI-context-to-discovery-state
translator (`travelerContextToPatch.test.ts`) and the PCM audio
encode/decode/resample math (`audioPlayback.test.ts`,
`pcmResample.test.ts`). Component rendering tests, Playwright/E2E, and
the Gemini Live WebSocket wrapper itself (`geminiLiveClient.ts`) are
explicitly out of scope for automated testing this phase.

**Why**:
- These specific pieces of logic are exactly the kind most likely to
  silently drift and violate a stated invariant without a human noticing
  in casual manual testing: the translator is the one place enforcing
  "the app controls DiscoveryState translation, never the model," and the
  PCM math (16kHz downsampling ratio, Int16 clamping, 24kHz buffer
  scheduling) is easy to get subtly wrong in a way that sounds fine on
  casual listening but is measurably incorrect
- Vitest was chosen over Jest specifically because it needs near-zero
  configuration against Next.js 16's Vite-adjacent tooling and has native
  ESM/TypeScript support, avoiding Jest's more involved Next.js transform
  setup — appropriate for a hackathon-timeline addition
- The Gemini Live WebSocket wrapper is integration-only by nature (it
  requires a real Gemini connection to meaningfully exercise session
  resumption, GoAway handling, and real audio round-trips) — automated
  unit tests around it would either be trivial (mocking away everything
  interesting) or require a real network dependency the test suite
  explicitly avoids elsewhere; it is covered by the mandatory manual
  verification checklist (ADR-035) instead

**Alternatives Considered**:
- No frontend tests at all (extend the "no prior framework" status quo):
  would leave the translator and PCM math — genuinely correctness-critical
  and non-obvious — completely unverified beyond manual listening/clicking
- Full component/E2E coverage (Playwright, React Testing Library) for the
  whole voice UI: valuable in principle, but disproportionate to a
  hackathon timeline and duplicates what manual verification already
  covers end-to-end; deferred, not rejected — a natural Phase 12
  ("Full Integration, Testing, Hardening") candidate

**Consequences**:
- `apps/web/package.json` gains `vitest`/`jsdom` devDependencies and a
  `test` script; `apps/web/vitest.config.ts` is the new minimal config
- `@types/node` was bumped from `^20` to `^24` to satisfy Vitest 5's peer
  dependency requirement — verified this doesn't affect `tsc --noEmit`,
  `next build`, or any Next.js-specific typing
- 20 new tests, all passing, run via `npm run test` (`npx vitest run`)
  alongside the existing `lint`/`tsc --noEmit`/`build` checks

---

## ADR-040: Semantic Embedding Adapter — Separate Interface, Gemini `gemini-embedding-2`, Deterministic Mock

**Decision**: `EmbeddingAdapter` (src/adapters/embedding.py) is a new,
separate interface from Phase 5's `AIAdapter` — not an added method on
it. It exposes explicit `embed_query`/`embed_document`/`embed_documents`
methods (asymmetric retrieval: query and document text are prompted
differently — `task: search result | query: {text}` vs
`title: {title} | text: {text}`). `GeminiEmbeddingAdapter` uses the
official `google-genai` SDK's `client.aio.models.embed_content(...)`
against `gemini-embedding-2` (configurable via `GEMINI_EMBEDDING_MODEL`),
output dimensionality configurable via `GEMINI_EMBEDDING_DIMENSIONS`
(default 1536). `MockEmbeddingAdapter` is a deterministic hash/token-
feature-based vector generator (NOT random, NOT ML) used for tests/CI/
no-key dev, selected by the same `GEMINI_ENABLED` + `GEMINI_API_KEY`
presence rule as `AIAdapter` (src/core/embedding.py mirrors
src/core/ai.py exactly).

**Why**:
- Embedding generation is a genuinely distinct capability from structured
  text generation and Live token issuance — conflating it into
  `AIAdapter` would mean every embedding call carries the Live/text
  adapter's unrelated surface area, and asymmetric retrieval needs the
  query-vs-document distinction to be a first-class part of the method
  signature, not just prompt text a caller might forget to vary
- A deterministic mock (not random) is required so retrieval-ordering
  tests are reproducible and meaningful — a random mock would make
  "candidate A should rank above candidate B" assertions flaky by
  construction
- Mirroring `src/core/ai.py`'s selection rule exactly (rather than
  inventing a second policy) keeps "when does LocaLens use real Gemini
  vs. a mock" a single mental model across both adapters

**Alternatives Considered**:
- Add `embed_*` methods directly to `AIAdapter`: rejected — bloats one
  interface with an unrelated capability and makes the query/document
  asymmetry easy to lose track of
- A single `embed(text)` method with a `mode` flag instead of two named
  methods: rejected — the explicit method names make the asymmetric
  intent impossible to call incorrectly by omission

**Consequences**:
- **NOT VERIFIED live** — no `GEMINI_API_KEY` is available in this
  environment; `GeminiEmbeddingAdapter` is implemented against the
  documented SDK surface (`embed_content`, `EmbedContentConfig` with
  `task_type`/`output_dimensionality`) and unit-testable error mapping,
  but has not been exercised against the real Gemini API
- `MockEmbeddingAdapter` is what all Phase 6 tests, the indexing script's
  default dev run, and CI exercise

---

## ADR-041: Dedicated `ExperienceEmbedding` Store — Portable JSON + pgvector Production Path

**Decision**: A new `ExperienceEmbedding` model/table (one row per
experience, unique FK with cascade delete) stores the embedding vector,
its model name, dimensionality, and a `source_content_hash` for
change-detection. The SQLAlchemy column is a portable JSON float-list
(works identically on SQLite and PostgreSQL). The Phase 6 Alembic
migration additionally branches on `bind.dialect.name`: PostgreSQL gets
`CREATE EXTENSION IF NOT EXISTS vector`, a native `vector(1536)` column,
and an HNSW cosine index; SQLite gets no vector DDL at all. Retrieval
(`SemanticRetrievalService`) branches the same way at query time: SQLite
loads a bounded candidate set and computes cosine similarity in Python
(`src/core/vector_math.py`); PostgreSQL queries the vector column
natively with `ORDER BY embedding_vector <=> :query` using the HNSW
index, entirely database-side.

**Why**:
- A separate table (not a column on `Experience`) keeps the
  embedding/model/dimensions/hash lifecycle independent of the
  experience's own read/write path, and makes "no embedding yet" a
  simple missing-row case rather than a nullable-column special case
- Storing the JSON representation unconditionally (even on PostgreSQL)
  means the ORM layer, the indexing script, and any future
  read-for-debugging code path never need dialect-specific branching —
  only the retrieval query itself does
- `source_content_hash` lets the indexing script be genuinely idempotent
  (skip-if-unchanged) without re-embedding the whole catalog on every run

**Alternatives Considered**:
- Store only the pgvector column type everywhere via a portable
  SQLAlchemy custom type: rejected — no verified production PostgreSQL
  instance was available to validate a custom `TypeDecorator` against;
  the explicit per-dialect branch in the migration and retrieval service
  is easier to reason about and to mark honestly as "SQLite verified,
  Postgres not"
- A SQLite vector extension (e.g. sqlite-vec): explicitly out of scope
  per the phase brief — no SQLite-vector extensions, Python cosine
  similarity over a bounded pool instead

**Consequences**:
- **NOT VERIFIED live** — no PostgreSQL instance is available in this
  environment. The pgvector migration branch and
  `EmbeddingRepository.search_similar_pgvector` are implemented against
  documented pgvector SQL syntax and read-reviewed, but never executed
  against a real PostgreSQL+pgvector database
- SQLite fresh-DB and seeded-dev-DB migrations were both verified
  (`alembic upgrade head`/`downgrade -1`/`upgrade head` again), with the
  existing 353 experiences / 311 providers confirmed unaffected

---

## ADR-042: Canonical Text Construction — Real Fields Only, Query/Document Asymmetry, Hard Constraints Excluded from Semantic Text

**Decision**: `build_experience_document_text` (src/services/embedding_text.py)
builds embedding input text only from fields that actually exist on the
stored `Experience`/`Location`/`ExperienceCategory` rows (title,
category, descriptions, tags, suitability, locality/city) — it never
adds rating, hours, availability, or accessibility text, because Phase 6
does not fabricate facts that are not genuinely present, and a missing
field is simply omitted from the text rather than filled with a
placeholder. `build_query_text` builds the traveler's query embedding
input from semantic-intent fields only (raw query, interests, category,
location text) — budget, duration, party size, travel constraints, and
accessibility requirements never enter the embedding text, because those
are hard constraints that belong exclusively to `FeasibilityService`.

**Why**:
- Stuffing a hard numeric constraint into a semantic embedding query
  would make the embedding degrade the very safety property Phase 6 is
  built around: a "cheap food" query embedding "close" to an expensive
  restaurant's embedding is a similarity artifact, not a feasibility
  signal — the constraint must be checked deterministically, never
  fuzzily via vector distance
- Keeping document text to real fields preserves the same
  never-fabricate invariant that already governs the rest of the catalog
  (docs/AI_CONTEXT.md) — an embedding is just another representation of
  the same underlying facts, not a new place to invent data

**Alternatives Considered**:
- Include a synthesized "typically costs ₹X, open until Y" sentence in
  document text to improve semantic matching: rejected outright — this
  is exactly the fabrication Phase 6 exists to prevent structurally, not
  just discourage by convention

**Consequences**:
- `is_synthetic` provenance is preserved on the returned
  `ExperienceDocument` dataclass (not folded into the prompt text itself)
  so downstream code can carry the distinction through without needing
  to re-derive it from the embedded text

---

## ADR-043: Deterministic Feasibility Engine — Tri-State Verdict, Hard Gate Before Any Ranking, No LLM Calls

**Decision**: `FeasibilityService` (src/services/feasibility.py) is 100%
deterministic — it makes zero LLM calls anywhere in its evaluation path.
Every constraint check returns one of: not applicable (traveler didn't
ask), FEASIBLE (passes), an explicit `INFEASIBLE` reason (data present,
constraint violated), or an `UNKNOWN` reason (required data missing —
never guessed, never defaulted to feasible). The overall verdict is
FEASIBLE only when zero blocking reasons of either kind were produced;
`UNKNOWN` can never be upgraded to `FEASIBLE` by any caller.
`DiscoveryPipelineService` places this engine as a hard gate immediately
after semantic retrieval and before any future ranking step — only
candidates verified FEASIBLE ever appear in a pipeline response's
`items`; excluded candidates are summarized (reason-code counts + a
capped sample) but never leak into the feasible set, and an
all-excluded result returns an empty `items` list rather than forcing a
lower-quality result through.

**Why**:
- A tri-state (not boolean) verdict is the only way to make "we don't
  know" structurally distinguishable from "we checked and it fails" —
  collapsing UNKNOWN into either FEASIBLE or INFEASIBLE would either
  silently promise something unverified or wrongly reject a candidate
  that might well be fine
- Placing the gate before ranking (rather than after, or interleaved)
  means Phase 7's future ranking model only ever sees verified-feasible
  candidates — ranking never has to re-litigate feasibility, and a
  ranking bug can never surface an infeasible result to a traveler
- Evaluating every applicable check (not stopping at the first failure)
  means a single API/tool call surfaces the complete picture instead of
  requiring the caller to fix one constraint and re-request repeatedly
  to discover the next blocking reason

**Alternatives Considered**:
- A boolean feasible/infeasible verdict with missing data defaulting to
  feasible: rejected — this is precisely the "invented feasibility"
  failure mode the phase brief calls out as a hard invariant
- Let a Phase 7 ranking step re-check feasibility itself as part of
  scoring: rejected — duplicates the check, risks drift between two
  implementations, and reopens the door to a ranking heuristic silently
  overriding a hard constraint

**Consequences**:
- 41 dedicated unit tests (tests/test_feasibility_service.py) cover every
  implemented check's pass/fail/unknown/boundary cases individually, plus
  multi-failure and tri-state-precedence cases; all pass on SQLite
- The itinerary-conflict check accepts `CommittedTimeBlock` list input
  directly (interval arithmetic only) — no `Itinerary`/`ItineraryItem`
  persistence model was added, since that composition layer is Phase 8's
  responsibility, not Phase 6's

---

## ADR-044: Centralized Reason-Code Enum + `check_feasibility` as a Second, Backend-Only Gemini Tool

**Decision**: Every code `FeasibilityService` can emit lives in one place
(`src/core/feasibility_reasons.py`, a `StrEnum`) — routes, the Gemini
tool, and the frontend's TypeScript mirror all reference this single
list rather than re-declaring string literals. `check_feasibility` is
added as the second Gemini tool alongside `search_experiences`
(`CHECK_FEASIBILITY_DECLARATION`/`execute_check_feasibility` in
src/services/ai_tools.py), registered in both the Live token's
`live_connect_constraints` tool list and the voice tool-call bridge's
allowlist. Its argument schema (`CheckFeasibilityArgs`, `extra="forbid"`)
accepts only an `experience_id` and constraint values (budget, time,
party size, travel, accessibility) — it has no field for price, hours,
capacity, or availability, so Gemini structurally cannot supply an
invented fact for any of those; the tool always loads the real
`Experience` row and runs the same `FeasibilityService` used by
`POST /api/v1/feasibility/check`. The Live system instruction (now
actually set via `types.Content`/`system_instruction` on
`LiveConnectConfig`, which Phase 5's ADR-037 described as policy but the
adapter had not yet wired into the SDK call) explicitly limits the model
to these two tools and forbids phrasing `UNKNOWN` as reassuring.

**Why**:
- A centralized enum is the only way "only document codes you actually
  implement" (the phase brief's explicit instruction) stays enforceable
  over time — a scattered set of string literals invites silent drift
  between what the engine emits and what routes/tools/UI claim to handle
- Giving Gemini no schema field for price/hours/capacity/availability is
  a stronger guarantee than telling it not to invent those values in a
  prompt — a field that doesn't exist in the validated schema cannot be
  smuggled through even if the model tries
- Fixing the Live system instruction gap (Phase 5 documented the policy
  in ADR-037 but the adapter never actually attached
  `system_instruction` to `LiveConnectConfig`) closes a real gap between
  documented and implemented behavior rather than layering Phase 6 on
  top of it unnoticed

**Alternatives Considered**:
- Let `search_experiences`' result carry an inline feasibility flag
  instead of a separate tool: rejected — conflates "find candidates"
  with "verify this one candidate," which the phase brief explicitly
  wants kept as two distinct steps for the model (and a human reading
  the tool-call log) to reason about separately

**Consequences**:
- `execute_search_experiences` itself is deliberately left as a thin
  wrapper around the Phase 4 keyword/geo discovery service — its
  argument schema carries no hard constraints, so there is nothing for a
  Phase 6 pipeline upgrade to change there; the text-turn orchestration
  (`handle_text_turn`) instead routes to `DiscoveryPipelineService`
  directly (bypassing the `search_experiences` tool schema entirely)
  whenever the extracted `TravelerContext` carries a hard constraint,
  producing a templated reply built from real feasible/excluded counts —
  never a second free-form Gemini call
- `TravelerContext` gained optional, nullable Phase 6 fields (currency,
  budget_min/max, available_date/start/end/duration, timezone,
  origin_lat/lng, travel_mode, max_distance_km,
  max_travel_time_minutes, accessibility_requirements,
  existing_commitments) — strictly additive, no Phase 5 field changed

## ADR-045: Two-Stage Deterministic Composer, No External Optimizer

**Decision**: `ExperienceComposerService` (`src/services/experience_composer.py`)
composes an itinerary in two deterministic stages over an already-ranked,
already-FEASIBLE candidate list (Phase 6 retrieval -> Phase 6 feasibility
-> Phase 7 ranking): (A) a greedy walk in Phase 7 rank order that checks
time window, travel time from the previous stop (via the existing
`RoutingAdapter` — never assumed to be 0 when unknown), opening-hours-
adjacent budget/duration fit, and overlap, appending whatever fits next;
(B) a bounded local-improvement pass (at most a fixed number of swap
attempts) that only ever replaces the single lowest-value selected item
with a strictly higher-`ranking_score` unused candidate when the swap
keeps the schedule valid and within budget. No external
optimization/solver library — the whole thing is a documented, bounded,
bounded-iteration Python loop. The composer never recomputes or mutates a
Phase 7 `ranking_score`; it only ever reads it as an ordering signal.

**Why**:
- The hard invariant "never compose an experience that isn't FEASIBLE"
  is trivially satisfied because the composer only ever sees candidates
  that already passed Phase 6 feasibility and were already ranked by
  Phase 7 — composition is a pure scheduling/selection problem on top of
  that, never a second feasibility judgment
- A bounded, deterministic loop is provably terminating and reproducible
  (same inputs -> same output, asserted directly by
  `tests/test_experience_composer.py::test_determinism_same_inputs_identical_output`)
  — an external solver would trade that reproducibility for opacity with
  no proportionate benefit at this candidate-set scale
- Treating an unknown travel-time transition as a hard skip (never 0
  minutes) is the same discipline Phase 6's `FeasibilityService` already
  applies to UNKNOWN — Phase 8 does not get to be looser about honesty
  than Phase 6 was

**Alternatives Considered**:
- A single-pass greedy composer with no improvement stage: rejected —
  would leave an obviously-better unused candidate on the table whenever
  the first-fit greedy choice was merely "good enough," with no
  mechanism to ever reconsider it
- A full constraint-solver (e.g. OR-tools) for optimal composition:
  rejected — disproportionate for a small (≤ `composer_max_candidates`)
  candidate pool, adds a new dependency and a harder-to-audit black box,
  and the phase brief explicitly calls for "no external optimization
  library, keep it a bounded, documented, deterministic loop"

**Consequences**:
- Objective hierarchy is fixed and documented in the module docstring:
  hard feasibility > aggregate ranking value > count within window >
  minimize travel time > minimize idle gaps > respect budget > category
  variety > experience-id tie-break — any future change to this ordering
  is a deliberate, reviewable diff to that one docstring, not an
  implicit behavior drift
- `ItineraryValidatorService` (ADR-046) is mandatory and independent —
  the composer's own checks are a performance/quality heuristic during
  selection, not the system's actual feasibility guarantee

## ADR-046: Mandatory Post-Composition Validator Reusing `FeasibilityReasonCode`; REQUESTED-Only Booking Lifecycle

**Decision**: `ItineraryValidatorService` (`src/services/itinerary_validator.py`)
re-runs after composition and before any narrative is generated —
never optional, never skippable. It re-evaluates every item's
underlying `Experience` against `FeasibilityService` at that item's own
scheduled slot (never trusting the composer's earlier snapshot alone,
since the DB may have changed), plus schedule-level checks (chronological
order, overlap including buffers, travel-time-transition known,
duplicate experiences, window bounds) and itinerary-level checks (budget,
count limit, non-empty). Every issue is reported using the existing
`FeasibilityReasonCode` enum from Phase 6 — extended with a handful of
itinerary/schedule-specific codes (`EXPERIENCE_NOT_FEASIBLE`,
`SCHEDULE_OVERLAP`, `TRAVEL_TRANSITION_IMPOSSIBLE`,
`DUPLICATE_EXPERIENCE`, `OUTSIDE_REQUESTED_WINDOW`,
`ITINERARY_BUDGET_EXCEEDED`, `ITINERARY_COUNT_LIMIT_EXCEEDED`,
`ITINERARY_EMPTY`, `SCHEDULE_NOT_CHRONOLOGICAL`, `INVALID_BUFFER`) —
never a parallel free-form string set. On INVALID, `compose_and_persist_itinerary`
(`src/services/compose_itinerary.py`) returns a structured
`CompositionValidationResponse` (`valid: false` + reason code + every
issue found) instead of ever forcing a partial plan through.

Separately: `BookingRequest.status` is a closed enum
(`REQUESTED`/`ACCEPTED`/`DECLINED`/`CANCELLED`/`EXPIRED`) with no
`CONFIRMED` value anywhere in the schema, model, or TypeScript mirror,
and no payment field exists on the model, schema, or API surface at all.

**Why**:
- Reusing `FeasibilityReasonCode` rather than inventing a second code
  taxonomy keeps "every reason the system can give a traveler" auditable
  from one file, matching the exact rationale ADR-044 already established
  for Phase 6 — Phase 8 is additive to that contract, not a fork of it
- Re-checking feasibility against the *scheduled* slot (not the original
  unscheduled constraint) closes a real correctness gap: an experience
  that was FEASIBLE for a loose "sometime today" constraint during
  retrieval can still turn out infeasible once the composer gives it a
  concrete 14:00-15:00 slot (e.g. outside opening hours at that specific
  time) — only the validator, running after scheduling, can catch that
- Making `CONFIRMED` structurally absent from the status enum (not just
  "unused by convention") means a future contributor cannot silently
  introduce a false confirmation claim without first changing this
  contract file, which is exactly the kind of accidental scope creep the
  phase brief's hard invariants exist to prevent

**Alternatives Considered**:
- Trust the composer's own in-loop feasibility checks as sufficient,
  skip a separate validation pass: rejected — the composer's checks are
  a selection heuristic scoped to "does this fit next," not a
  from-scratch verification of the whole finished schedule; a
  local-improvement swap (stage B) could in principle introduce an issue
  stage A never had to consider
- Add a `CONFIRMED` status now with an explicit "never set it" comment,
  planning to wire real payment/confirmation flows later: rejected — an
  achievable-but-unused enum member is exactly the kind of thing that
  gets set accidentally under deadline pressure; Phase 8 has no payment
  processing in scope at all, so the value should not exist yet

**Consequences**:
- `compose_and_persist_itinerary` retries are bounded to the composer's
  own single deterministic pass (stage A + stage B) — if that pass's
  result is INVALID, the whole compose request fails honestly rather
  than looping the composer indefinitely trying alternate combinations
- Every itinerary-related test (`test_itinerary_validator.py`,
  `test_itinerary_api.py`, `test_booking_api.py`) explicitly asserts an
  INFEASIBLE/UNKNOWN item is never accepted and that REQUESTED/ACCEPTED
  are never rendered as confirmed — this is a permanent regression gate,
  not a one-time check

## ADR-047: Gemini Narrative Layer Is Purely Decorative — Facts-Only Prompt, Deterministic Template Fallback

**Decision**: `ItineraryNarratorService` (`src/services/itinerary_narrator.py`)
reuses the existing `AIAdapter` (`src/adapters/ai.py`) — no second AI
client. Its prompt contains only backend-validated facts (already-VALID
itinerary items' real ids/titles/prices/times/travel-gaps/booking
status) and an explicit anti-hallucination system instruction forbidding
invented prices/hours/reviews/availability/transport-time/locations and
forbidding any booking-confirmation claim beyond what the backend status
actually says. The structured `NarrativeResponse` (Pydantic, validated
via the same `generate_text(..., response_schema=...)` pattern Phase 5/6
already use) is post-processed to drop any `item_narratives` entry whose
`experience_id` was not in the supplied fact set — a hallucinated id is
silently dropped, never surfaced. On any Gemini failure (adapter error,
timeout, or invalid structured output), a deterministic backend template
(`_template_fallback`) produces the narrative instead — the itinerary's
validity and persistence never depend on Gemini succeeding.

**Why**:
- The phase brief's ordering invariant (RETRIEVAL -> FEASIBILITY ->
  RANKING -> COMPOSITION -> POST-COMPOSITION VALIDATION -> NARRATIVE)
  places narrative strictly last and non-authoritative — this is not
  just documentation, it is enforced by construction: the narrator's
  only inputs are already-validated `ComposedItem`s, so there is no
  code path by which Gemini's text could influence what gets scheduled
  or persisted
- Dropping (not repairing or trusting) a hallucinated `experience_id`
  keeps the same "structurally cannot smuggle a fact" discipline ADR-044
  established for `check_feasibility`'s argument schema — here it is
  the *output* schema that gets the same treatment
- A template fallback that always succeeds (even for zero items) means
  "Gemini is unconfigured/down" is never a reason a traveler cannot get
  a usable itinerary, matching the adapter-fallback contract already
  established for every other AI/location adapter in this codebase

**Alternatives Considered**:
- Let a Gemini failure fail the whole compose request: rejected — would
  make an entirely deterministic, already-correct itinerary unusable
  because of an unrelated third-party outage, directly contradicting the
  existing "the app must work with Gemini disabled" contract
- Ask Gemini to also select/order experiences via free text, then parse
  its output into the schedule: rejected outright by the phase brief's
  hard invariants — Gemini is never authoritative for feasibility,
  timing, or booking state

**Consequences**:
- `Itinerary.narrative_model_version` is deliberately a distinct string
  from `Itinerary.ranking_model_version` (`"gemini-narrative-v1"` /
  `"template-fallback-v1"` vs Phase 7's `"weighted-v1"`) — the two
  version fields must never be conflated since they describe unrelated
  subsystems with unrelated failure modes
- `tests/test_itinerary_narrator.py` mocks `AIAdapter` entirely — no
  live Gemini call in the automated test suite, matching every other
  Phase 5/6 AI test in this repo

## ADR-048: `compose_experience` Tool Reuses the Conversation's Cached Candidate Context — Never a Blind Second Pipeline Pass

**Decision**: `ConversationSession` gains one new JSON column,
`last_search_candidates` — a snapshot of the most recent
`search_experiences` tool call's ranked+feasible result for that specific
conversation, overwritten on every new search. `execute_compose_experience`
(`src/services/ai_tools.py`) validates every `experience_id` Gemini
supplies against this cached context (an id not present there is
silently dropped, never trusted) and, only when no context exists yet,
triggers exactly one fresh Phase 6+7 pipeline pass of its own — it never
re-runs retrieval/feasibility/ranking when a context already exists. This
mechanism is a minimal, additive extension of the exact JSON-snapshot
pattern Phase 5 already established for `latest_traveler_context` on the
same model, not a new parallel state-storage design.

**Why**:
- The phase brief requires the tool to "verify any experience_ids Gemini
  supplies belong to the current conversation's authorized ranked-
  candidate context" — extending the conversation's own existing
  session-scoped JSON snapshot mechanism is the natural fit, rather than
  inventing a second cache (e.g. Redis, a new table) for what is
  fundamentally the same kind of per-conversation ephemeral state
  `latest_traveler_context` already models
- The "never redundant when a context already exists" requirement is a
  direct instance of the same Phase 7 preflight invariant (retrieval +
  feasibility execute exactly once per logical request) this phase's
  preflight gate already re-verified and regression-tested — extending
  that discipline to the new tool rather than introducing an exception
  to it keeps the whole pipeline's execution-count guarantee uniform
- Silently dropping an unauthorized id (rather than erroring the whole
  compose call) matches how `search_experiences`' own argument
  validation already treats an unrecognized `category_slug` (ADR-034/035
  precedent: drop what cannot be trusted, don't fail the whole turn over
  one bad field)

**Alternatives Considered**:
- Trust `experience_ids` from Gemini directly, re-fetch each by id: 
  rejected — this is exactly the "trusting raw ids Gemini supplies
  blindly" the phase brief explicitly forbids; an id Gemini fabricates
  or misremembers from an earlier turn would otherwise silently reach
  the composer
- Store the candidate context in `ConversationMessage.tool_call_metadata`
  instead of a new `ConversationSession` column: rejected — that column
  already exists as a bounded observability record for the transcript
  and is not queried as "the current state"; a dedicated session-level
  field keeps "what is Gemini currently allowed to compose from" a single
  well-defined lookup rather than "scan recent messages for the last
  matching tool call"

**Consequences**:
- `tests/test_compose_experience_tool.py::test_no_duplicate_pipeline_execution_when_context_exists`
  is the permanent regression proof for this invariant — it patches
  `DiscoveryPipelineService.run` process-wide and asserts zero calls when
  a context already exists, mirroring the same call-counting technique
  `tests/test_pipeline_single_execution.py` uses for the Phase 7 preflight
- `last_search_candidates` is added via the same Phase 8 Alembic
  migration as the new itinerary/booking tables (`8a004268dcb0`) rather
  than a separate migration, since it is a small additive column on an
  existing table with no data-migration concern

---

## ADR-049: Real-Time Weather/Event Adapters Follow the Exact Phase 4 Adapter Pattern — No New Transport Layer

**Decision**: `src/adapters/weather.py` (`OpenWeatherAdapter`) and
`src/adapters/events.py` (`TicketmasterEventAdapter`) are built on the
identical foundation Phase 4's `OSRMRoutingAdapter`/
`NominatimGeocodingAdapter` already established: the shared
`src/core/http_client.py` httpx client, `IntervalRateLimiter`,
`TTLCache`, and the `src/adapters/errors.py` typed error hierarchy
(`AdapterTimeoutError`/`AdapterRateLimitedError`/`AdapterUnavailableError`/
`AdapterNoResultError`). A new `src/core/context.py` mirrors
`src/core/location.py`'s `lru_cache`-singleton, settings-gated
real-vs-mock selection exactly (`CONTEXT_SERVICES_ENABLED` +
key-presence, not a new gating mechanism).

**Why**: The phase brief explicitly requires "following the exact same
adapter pattern already used by routing.py/geocoding.py" — reusing the
existing transport/caching/rate-limiting/error primitives keeps external
outbound calls to one consistent surface (one place to add a global
timeout change, one error taxonomy the route layer already knows how to
translate) rather than a second bespoke HTTP layer for Phase 9.

**Alternatives Considered**:
- A dedicated `httpx.AsyncClient` per weather/event adapter: rejected —
  violates the established "never a new AsyncClient per adapter"
  invariant (ADR-022) with no benefit, since both providers' rate/timeout
  needs fit the same shared-client model.
- A generic `ExternalApiAdapter` base class factoring out the
  request/error-translation boilerplate: considered, deferred — Phase 6/7/8
  never introduced one despite three prior adapters sharing the same
  shape; introducing an abstraction now, for only two more adapters, adds
  indirection without a demonstrated third consumer.

**Consequences**:
- `tests/test_weather_adapter.py`/`tests/test_event_adapter.py` reuse
  `tests/adapter_fakes.py`'s `FakeAsyncClient` unchanged (one small
  addition: `.get()` now also accepts an optional `timeout=` kwarg, since
  the real adapters set an explicit per-request timeout) — no new test
  infrastructure needed.
- Neither adapter is verified against its live API in this worktree — no
  `OPENWEATHER_API_KEY`/`TICKETMASTER_API_KEY` available; this is
  explicitly reported as NOT VERIFIED, following the same convention
  Phase 6/7/8 used for their own unverifiable pieces (no Gemini key, no
  Postgres instance).

---

## ADR-050: Experience Environmental Metadata Is Additive-Only, Defaults to UNKNOWN — Never Inferred for Existing Rows

**Decision**: `Experience` gains three new columns —
`environmental_type` (INDOOR/OUTDOOR/MIXED/UNKNOWN),
`weather_sensitivity` (LOW/MEDIUM/HIGH/UNKNOWN), `weather_policy`
(NONE/LIGHT_RAIN_OK/WEATHER_SENSITIVE/SEVERE_WEATHER_EXCLUDE) — each
defaulting to UNKNOWN/NONE at the database level via an explicit
`server_default` in the migration, so every catalog row seeded before
Phase 9 (all 353 Overture-derived + synthetic experiences) is UNKNOWN by
construction, never silently guessed as e.g. OUTDOOR from its category
name.

**Why**: The phase brief is explicit — "if metadata unavailable → UNKNOWN,
never invented" — and this project's Phase 6 UNKNOWN-is-never-upgraded-
to-FEASIBLE contract is the direct precedent: `WeatherImpactService`
(src/services/weather_impact.py) treats UNKNOWN identically whether the
column was never backfilled or is genuinely not knowable for that
experience, exactly mirroring how `FeasibilityService` treats a missing
constraint fact.

**Alternatives Considered**:
- A separate `ExperienceEnvironmentalProfile` joined table: rejected —
  three small enum columns don't warrant a second table and a join on
  every feasibility/weather-impact check; `ProvenanceMixin` already
  establishes the "columns directly on the entity, not a satellite table"
  precedent for exactly this kind of per-record metadata.
- Inferring `environmental_type` from `ExperienceCategory` (e.g.
  "hiking" → OUTDOOR): rejected — the brief explicitly forbids inventing
  this value, and a category-based heuristic would be exactly that kind
  of invention, silently wrong for mixed-use venues.

**Consequences**:
- Every experience seeded before this migration ran is WEATHER_UNKNOWN
  until explicitly curated — `WeatherImpactService` and
  `ContextImpactService` are the only two places this matters, and both
  already treat UNKNOWN as "cannot assess, never treat as GOOD."
- A curation/back-fill pass (e.g. deriving environmental_type from
  Overture Places category tags where confidently mappable) is
  explicitly out of Phase 9 scope — noted as a PARTIAL/future item, not
  attempted here to avoid inventing a heuristic the brief forbids.

---

## ADR-051: `ItineraryRevision` + `Itinerary.version`/`current_revision_id` — Extend, Don't Duplicate the Itinerary Domain

**Decision**: Versioning/replanning state is split between (a) four new
columns directly on `Itinerary` (`version`, `current_revision_id`,
`replanning_status`, `context_last_updated_at`) and two on `ItineraryItem`
(`is_locked`, `item_state`) for hot-path reads, and (b) one genuinely new
table, `ItineraryRevision`, for the append-only history a single mutable
counter cannot represent (trigger, previous/new version, normalized
change set, idempotency key). `ContextSnapshot` is a second new table,
used only for replan traceability/audit — the hot-path weather/event
lookup itself still goes through `TTLCache` inside the adapters, never
through this table.

**Why**: The phase brief's own guidance — "prefer extending
Itinerary/ItineraryItem ... but add ItineraryRevision/ContextSnapshot ...
where the spec requires persisted history" — is a direct decision rule:
version/locking/status are single-value-per-itinerary facts that belong
on the row itself (matching how `Itinerary.status`/`ranking_model_version`
already work), while a revision is inherently a growing, ordered history
that a single mutable column cannot hold without erasing the previous
entry — exactly the "never silently mutate history" hard invariant.

**Alternatives Considered**:
- Storing the full previous itinerary state as a JSON blob on each
  revision (a true snapshot/diff log): rejected as unnecessary for this
  phase's scope — `ItineraryRevision.changes` records only the normalized
  added/removed/moved/unchanged/affected item-id sets, which is
  sufficient for the "what changed" UI and audit trail the spec asks for,
  without duplicating the entire itinerary schema inside a JSON column.
- A single `itinerary_revisions` table with no `Itinerary.version` column
  (derive "current version" via `MAX(version) WHERE itinerary_id = ...`
  on every read): rejected — the optimistic-locking check
  (`expected_version` vs current) is on the hot path of every replan
  request; a denormalized counter column avoids an extra query there and
  matches how `Itinerary.status` already denormalizes "current state."

**Consequences**:
- `(itinerary_id, idempotency_key)` carries a unique constraint on
  `ItineraryRevision` — SQLite/Postgres both treat multiple NULL values
  in a unique constraint as distinct, so non-idempotent replans (no key
  supplied) never collide with each other.
- Migration `04763f8eec67` (head was `8a004268dcb0`) adds explicit
  `server_default` values for every new NOT NULL column so it applies
  cleanly to the already-seeded 353-experience/multi-itinerary dataset,
  not just an empty database — verified via upgrade→downgrade→upgrade
  against a fresh SQLite DB plus a full seed run in this worktree.

---

## ADR-052: SSE (Not WebSocket) for Live Itinerary Updates, In-Process Pub/Sub Bus — Single-Process Limitation Documented, Not Solved

**Decision**: `GET /api/v1/itineraries/{id}/updates` is a Server-Sent
Events stream (`src/services/sse.py`), not a WebSocket — this codebase
has no existing WebSocket infrastructure anywhere (confirmed by
inspection), and the data flow is one-directional (backend → client)
plus occasional manual REST calls for anything the client needs to send,
which SSE's simpler request/response-shaped model fits without adding a
new bidirectional protocol stack for a single new feature. The event bus
is an in-process `dict[itinerary_id, list[asyncio.Queue]]` — genuinely
single-process, matching how this app currently runs
(`scripts/dev.ps1`/`dev.sh` launch one uvicorn process; nothing in this
repo evidences a multi-worker production deployment).

**Why**: Matches the phase brief's own instruction to confirm no existing
WebSocket infra and "proceed with SSE per the spec regardless." Building
a distributed pub/sub layer (Redis, etc.) for a feature with no
multi-worker deployment target anywhere in this codebase would be
over-engineering relative to what Phase 9 actually needs to demonstrate;
the limitation is instead explicitly documented (`ContextMonitor`'s
docstring, docs/PROJECT_STATE.md) rather than silently ignored or
half-solved.

**Alternatives Considered**:
- WebSocket with a custom message envelope: rejected per the brief;
  would also require new client-side connection-lifecycle code with no
  corresponding server-side benefit given the one-directional event
  shape.
- A Redis-backed pub/sub bus from the start: rejected as premature —
  this repo has no Redis dependency anywhere else (ADR-022's cache is
  explicitly "prototype-grade, single-process"); adding one just for SSE
  fan-out, with no second process to fan out to, would be unused
  complexity.

**Consequences**:
- A second uvicorn worker/process would not receive events published in
  another process — explicitly out of scope, documented as a known
  limitation rather than fixed here.
- The frontend SSE client (`apps/web/lib/api/itineraryUpdates.ts`) uses
  `fetch()`+`ReadableStream` rather than the browser `EventSource` API,
  because `EventSource` cannot send a custom `Authorization` header and
  this endpoint is `require_traveler`-gated like every other authenticated
  route — a deliberate, documented deviation from the "usual" SSE client
  API, not an oversight.

---

## ADR-053: `replan_experience` Never Directly Mutates — Delegates Entirely to `ReplanningService`, the Same Path as the Manual REST Endpoint

**Decision**: The fourth Gemini tool, `replan_experience`
(`src/services/ai_tools.py::execute_replan_experience`), accepts only
`itinerary_id`, an optional `affected_experience_id` hint, a free-text
`requested_change`, and optional time/budget/party-size hints — never
`traveler_id` (server-derived from the authenticated conversation, exactly
like `compose_experience`) and never a final itinerary state or booking
confirmation. It constructs a `USER_REQUESTED`-trigger
`ContextImpactResult` and calls `ReplanningService.replan_itinerary()` —
the identical call the manual `POST /itineraries/{id}/replan` REST
endpoint makes; there is exactly one replanning code path, never a
Gemini-specific shortcut.

**Why**: Direct continuation of the Phase 6 (`check_feasibility`) and
Phase 8 (`compose_experience`) precedent — every Gemini tool is a thin,
argument-validated bridge to a deterministic backend service Gemini never
gets to bypass or duplicate. Routing through `ReplanningService` means
every invariant that service already enforces (locked-item protection,
completed-item immutability, full re-validation, revision history) applies
identically whether the replan was requested via REST or voice — no
second, weaker enforcement path for the voice channel.

**Alternatives Considered**:
- Let Gemini directly propose specific replacement experience ids to
  swap in: rejected — the brief is explicit that Gemini "never decides
  ... whether to remove an experience"; `affected_experience_id` is
  accepted only as a hint that is never trusted to bypass Phase 6
  feasibility/Phase 7 ranking/Phase 8 composition.
- A separate `GeminiReplanningService` tuned for conversational context:
  rejected outright per the phase brief's explicit "never create a
  DynamicRanker/ReplanningRanker" instruction (generalized here to never
  creating a second replanning entry point of any kind).

**Consequences**:
- `tests/test_replan_experience_tool.py` includes a static-source check
  (`execute_replan_experience`'s source must reference
  `ReplanningService.replan_itinerary` and must never call
  `session.add(ItineraryItem(...))` directly) as a structural regression
  guard against a future edit accidentally adding a direct-mutation
  shortcut.
- The Live voice system instruction (`src/adapters/ai.py`) was updated to
  list `replan_experience` as the fourth and final Phase 9 tool, with
  explicit language that Gemini must report `REPLAN_FAILED`/
  `REQUIRES_USER_ACTION` honestly rather than claiming success. Task 4 later
  adds `simulate_what_if` as a fifth, read-only preview tool; it cannot apply
  or persist a plan change.

---

## ADR-054: Feasibility Opening-Hours/Availability Checks Distinguish "Precise Window" (Containment) from "Date-Only" (Overlap) — and the Composer Gets a Bounded Post-Validation Retry

**Decision**: `FeasibilityService._check_opening_hours` and
`_check_availability` now branch on whether the caller supplied a
specific `available_start`/`available_end` (a "precise window") or only
`available_date`. A precise window keeps the original semantics: the
experience's opening hours/availability slot must fully *contain* the
given window — correct for verifying one specific visit (the standalone
`POST /api/v1/feasibility/check` endpoint, and the mandatory
post-composition per-item re-check in `ItineraryValidatorService`, which
always supplies the item's own precise `planned_start`/`planned_end`). A
date-only constraint — used by the itinerary composer's whole-day
candidate gate in `compose_itinerary.py`, before any specific slot has
been chosen for a candidate — now means "is this open/bookable at all
that day" (any overlap), not "is this open across the traveler's entire
requested day." Additionally, `compose_itinerary.py`'s composition step
is now a bounded retry loop (`Settings.composer_max_validation_retries`,
default 5): when the post-composition validator rejects a specific item
as no-longer-feasible at its assigned slot, that one experience id is
excluded from the candidate pool and composition is retried from
scratch, rather than failing outright on the first rejection.

**Why**: Discovered live, not in the automated test suite — a real
compose request against real seed data with real opening-hours rows
(most venues open 10:00–19:00, not 24 hours) failed 100% of the time
with `feasible_count: 0`, because the candidate gate was defaulting an
omitted start/end to a synthetic `00:00`–`23:59` window and then
requiring full containment of that entire day, a bar essentially no real
business can clear. Once that was fixed and a `feasible_count > 0`
candidate pool existed, composition *still* failed outright the first
time the greedy scheduler placed a candidate into a slot its precise
hours didn't cover (e.g. scheduling the very first item to start exactly
at the traveler's 9am window-open, when the venue opens at 10am) —
because nothing ever retried, despite the Phase 8 brief's own spec
describing "bounded deterministic alternatives" as the required behavior
for exactly this case. Both fixes were necessary together: the overlap
check alone still leaves the *scheduler* free to pick a slot a candidate
doesn't actually fit; the retry alone would have had to churn through
nearly the entire feasible pool on a full-day-containment-first
composer without ever getting real signal on which candidates were
genuinely close to feasible.

**Alternatives Considered**:
- Make the composer's greedy scheduler call `FeasibilityService.evaluate()`
  directly for each candidate at its proposed slot, before committing it:
  more precise (would avoid the retry loop entirely), but requires
  fetching the full `Experience` ORM row per candidate during scheduling
  (the composer currently only has the lighter `RankedExperienceItem`
  API-facing summary, which doesn't carry raw opening-hours rows) — a
  real, larger change deferred rather than done under live-debugging
  time pressure. The retry loop is correct and bounded in the meantime;
  a future pass could add pre-slot verification as a scheduling-quality
  improvement without changing the overlap/containment fix.
- Relax `_check_opening_hours`/`_check_availability` to overlap semantics
  everywhere, including the precise-window case: rejected — this would
  weaken the standalone single-experience feasibility guarantee that
  `check_feasibility` (the Gemini tool) and manual booking-request
  creation both depend on being exact.

**Consequences**:
- The distinction is keyed purely on `constraints.available_start is
  not None` — any future caller that wants the strict precise-window
  semantics must supply a real start/end, not rely on a default.
- `docs/CHANGELOG.md`'s 2026-09-25 debugging-session entry documents the
  live symptoms (`candidate_count: 341, feasible_count: 0` →
  `feasible_count: 17` after the overlap fix → a real composed itinerary
  after the retry-loop fix) that led to this ADR.
- A new idempotent script, `scripts/seed_availability.py`, was added
  alongside this fix to backfill demo `ExperienceAvailability` rows from
  existing opening-hours data — the seed catalog had zero such rows,
  which was a separate, compounding gap (see CHANGELOG) rather than a
  defect in this feasibility logic itself.

## ADR-055: Phase 0-9 Reconciliation — Real Bugs Found via mypy/ruff and Live Verification, a Vacuous-Test-Coverage Fixture Gap, and an SSE Test-Harness Limitation

**Status**: Accepted

**Context**: A full reconciliation pass (static analysis with `mypy
--strict`/`ruff`, plus live smoke tests against real Gemini/OpenWeather/
Ticketmaster credentials) was run across the whole backend after Phase
9 to establish the actually-verified state of the codebase, independent
of what earlier phase docs claimed. This surfaced several real,
previously-undetected defects, none reachable from the existing test
suite because the suite itself had a silent coverage gap (below).

**Decision / Findings**:

1. **Ranking budget filter never applied** (`src/services/ranking.py`).
   `WeightedPersonalizedRanker` read `context.constraints.budget_max`,
   a nested shape that only exists on the separate `TravelerConstraints`
   schema used by the Phase 6 feasibility pipeline — `TravelerContext`
   (what ranking actually receives) carries `budget_max` as a flat
   field. The attribute access silently returned an `AttributeError`-free
   *wrong* value in the untyped path, or would have crashed under
   `TravelerContext.model_validate`-enforced typing; either way the
   budget penalty never fired. Fixed to read `context.budget_max`
   directly. Found by `mypy --strict`, not by any existing test.

2. **API keys leaking into plaintext logs** (`src/core/logging.py`).
   `httpx`'s request-logging uses a `%s`-style template with the actual
   URL stored in `record.args`, not `record.msg` — a filter that only
   inspected `record.msg` missed the real querystring, including
   OpenWeather's `appid=` and Ticketmaster's `apikey=`. Fixed with a
   `_RedactSecretsFilter` that calls `record.getMessage()` (the
   already-substituted string) and attaches directly to
   `logging.getLogger("httpx")` rather than only to a root handler,
   because `configure_logging()`'s existing `if root.handlers: return`
   guard was skipping filter attachment whenever uvicorn had already
   configured root handlers before app startup ran. Verified live: a
   real OpenWeather and Ticketmaster call each logged with
   `appid=***REDACTED***` / `apikey=***REDACTED***` instead of the raw
   key.

3. **Replanning offset-naive/aware datetime crash and a double
   sequence_order collision** (`src/services/replanning.py`). SQLite
   silently strips tzinfo from `DateTime(timezone=True)` columns on
   round-trip, and the codebase has two different unwritten conventions
   for what a naive value read back from the DB means (UTC, for
   `ExperienceAvailability`/`feasibility.py`; local Asia/Kolkata, for
   `ItineraryItem`/`ExperienceComposerService`). `ReplanningService`
   compared `item.planned_start`/`planned_end` directly against
   timezone-aware `now`, crashing with `TypeError: can't compare
   offset-naive and offset-aware datetimes` the moment any real
   itinerary item was evaluated. Fixed with local
   `_planned_start`/`_planned_end` closures (and an equivalent inline
   conversion in the module-level `_item_to_composed`) that attach the
   local-Kolkata tzinfo only for comparison purposes, deliberately
   without mutating the ORM objects (to avoid spurious dirty-tracking
   UPDATEs). Separately, re-numbering `sequence_order` on kept items
   after a replan collided with newly-inserted composer items (both
   numbered from 1), and — because SQLite checks UNIQUE constraints
   immediately per statement rather than deferring them like PostgreSQL
   — even a same-batch renumber of kept items alone could transiently
   collide depending on UPDATE execution order. Fixed via offsetting
   new items past the kept count, and via a two-phase
   negative-placeholder-then-final renumber for the kept items.

4. **Unvalidated stored conversation context crashes tool-call ranking**
   (`src/api/v1/conversation.py`). `conversation.latest_traveler_context`
   is a raw JSON `dict` persisted from an earlier turn; it was passed
   directly as `context=` into the ranking pipeline, which assumes a
   `TravelerContext` object (see finding 1) — reproduced live as
   `AttributeError: 'dict' object has no attribute 'budget_max'` at
   `ranking.py:71` whenever a prior turn had stored a budget constraint.
   Fixed by validating with `TravelerContext.model_validate(...)` before
   use. A regression test,
   `test_tool_call_search_experiences_with_stored_budget_context_does_not_crash`
   in `tests/test_conversation_api.py`, was added and confirmed to fail
   against a temporarily-reverted fix before confirming it passes
   against the real one.

5. **Vacuous test coverage from an empty availability fixture**
   (`tests/conftest.py`). The `discovery_dataset` fixture seeded
   experiences with zero `ExperienceOpeningHour`/`ExperienceAvailability`
   rows, so every `/itineraries/compose` call in the test suite returned
   `feasible_count: 0` and composition always failed. Roughly 15+ tests
   across `test_replanning.py`, `test_itinerary_sse.py`, and others had
   `if "items" not in body: return` early-return guards intended for
   genuinely-infeasible edge cases, which instead silently no-op'd on
   every run, never executing their real assertions. This was not
   caught by CI passing, because the suite never failed — it just
   quietly skipped its own logic. Fixed by seeding real opening-hours
   (all experiences open all week) and a two-year-wide
   `ExperienceAvailability` window in the fixture, so composition
   actually succeeds and the guarded assertions genuinely run. Chosen
   deliberately over the lighter alternative of just documenting the
   gap, per explicit instruction to fix the fixture rather than leave
   the hole in place.

6. **SSE `TestClient` streaming hangs on the endpoint's infinite
   `while True` generator** (`tests/test_itinerary_sse.py`). The
   `/itineraries/{id}/updates` route streams indefinitely by design
   (heartbeats every 15s until the client disconnects — see
   `src/services/sse.py`), and is confirmed working correctly against a
   real running uvicorn process via manual `curl` verification. Reading
   its body through Starlette's in-process ASGI `TestClient` transport,
   however, reliably hung the test process — even bounded by a line
   count, even from a background thread with a join timeout, even
   without reading the body at all past opening the stream context
   manager. This looks like an ASGI-transport/anyio interaction the
   harness doesn't handle cleanly for a never-closing generator, not an
   application defect. `test_sse_owner_connects_and_gets_connected_event`
   was rewritten to call the route's real ownership-check and
   `StreamingResponse` construction directly (the same code the actual
   endpoint runs before handing off to the infinite generator) without
   ever opening a `TestClient` stream — the specific thing that hangs.
   The other four SSE tests were already hang-free (they use finite
   `.get()` calls or drive `sse_updates_stream()`/
   `publish_itinerary_event()` directly via `asyncio.run()`, with no
   HTTP involved) and were left unmodified.

**Why**: All six were found through genuine verification work (static
typing, live credentialed API calls, and root-causing a real process
hang), not hypothesized — consistent with this reconciliation's
no-fabrication requirement. Items 1-4 are real production bugs that
would have shipped silently; item 5 explains why the test suite didn't
catch them sooner; item 6 is a test-infrastructure limitation worth
recording so nobody re-attempts the same hung approach later.

**Alternatives Considered**:
- For item 6, keep debugging `TestClient.stream()` (thread+queue
  timeout wrapper, `httpx`-level `timeout=`, reading zero bytes):
  rejected after repeated confirmed hangs — reasonable engineering time
  was spent and the direct-invocation approach fully exercises the same
  route logic without the transport's failure mode.
- For item 5, leave the fixture as-is and just document the gap in
  CHANGELOG: rejected — the whole point of ~15 of those tests is to
  exercise composition-dependent behavior; documenting instead of
  fixing would leave that coverage permanently vacuous.

**Consequences**:
- Full backend suite: 361 passed, 0 failed, 0 hangs, 65.06s
  (`python -m pytest -q`), confirmed clean on 2026-09-25.
- `docs/CHANGELOG.md`'s reconciliation entry cross-references this ADR
  for the same six findings.
- The two conflicting naive-datetime conventions (item 3) remain
  unresolved by design — this ADR only fixes the crash at the
  comparison sites it touches; a future pass could standardize on one
  convention (e.g. always store/compare UTC) but that is a larger,
  out-of-scope migration under this reconciliation's minimal-fix rule.
- mypy --strict still reports two known, verified-safe-at-runtime gaps
  left intentionally unfixed: a dict-unpacking variance warning at
  `ranking.py:140` constructing `RankedExperienceItem(**exp_dict, ...)`,
  and ~18 "Item None of Traveler | None" warnings across
  `bookings.py`/`feedback.py`/`itineraries.py`/`recommendations.py`
  wherever `user.traveler.id` is read — safe because
  `UserRepository._base_query()` always eager-loads `User.traveler` via
  `selectinload` for a traveler-role user, so it is never actually
  `None` at those call sites at runtime. Both are annotation-precision
  gaps, not behavior bugs, and were left as-is per the "minimal fix,
  don't rewrite working subsystems" rule.

## ADR-056: Trip Draft Previews Stay Non-Persistent; Personal Stops Stay Additive

**Status**: Accepted

**Context**: The Trips composer previously kept selected places only in
client state until submission. Users needed a live ordered schedule,
date-specific feasibility previews, location-aware category filters,
and a way to include personal stops without inventing catalog records.
Recommendation labels also need to remain tied to evidence already
present in the catalog.

**Decision**:
- Keep draft and idea previews read-only. They calculate ordered times,
travel estimates, opening-hour/availability checks, time totals, and
cost totals from the selected date and catalog records; only the
existing compose action persists an itinerary.
- Store user-authored activities and notes in a separate additive
`itinerary_custom_activities` table. Do not create or alter canonical
`Experience` rows for them.
- Filter category chips by active real catalog records in the chosen
area. Search synonym/typo handling and recommendation ranking remain
deterministic and use catalog attributes.
- Show rating/popularity labels only when a rating source is explicitly
trusted. Missing evidence stays missing; synthetic ratings are marked
as demo data.

**Consequences**:
- Existing itinerary and experience records remain readable without
rewriting them; migration `9d3a7c4e1b20` adds only nullable budget data
and the custom-activity table.
- A custom physical stop can be scheduled and costed, but route travel
to or from it is reported as unverified until a canonical place can be
matched.
- Generated ideas are suggestions only when every included place
  passes the same date-specific feasibility checks used by the composer.

## ADR-057: Itinerary Maps Reuse the Existing Map and Context APIs

**Status**: Accepted

**Context**: Travelers need a spatial view of saved itinerary stops, selected
and affected state, route geometry, weather context, and explicit nearby
exploration. Discovery and experience pages already rely on a shared
MapLibre `MapSurface`, and the backend already owns route, nearby, and weather
contracts.

**Decision**:
- Extend `MapSurface` with optional generic annotation, route geometry,
  focus, and fit props. Keep itinerary semantics in the traveler-facing
  `ItineraryMap` wrapper rather than teaching `MapSurface` about itinerary
  records.
- Use only saved coordinates, call the existing typed location/weather APIs,
  load consecutive route legs sequentially on request, and draw only OSRM
  geometry. Do not infer coordinates or draw estimated straight-line routes.
- Keep weather map tiles disabled unless a server-side tile adapter and
  verified provider configuration become available. Tile facts and normalized
  weather context remain separate concerns.

**Consequences**:
- No route, weather, geocoding, POI, or persistence endpoint was added; no
  database migration is needed.
- Discovery keeps its clustered experience source, search-this-area flow,
  and existing route behavior. Existing OSRM and OpenWeather adapters remain
  authoritative.
- Itinerary text remains usable without the map and includes route/weather
  status. Device geolocation and background tracking are not introduced.

## ADR-058: Public Social Context Is Opt-In, Aggregated, Area-Level, and Advisory

**Status**: Accepted

**Context**: Task 3 asks to show public social signals beside existing
weather and itinerary context. This repository has no existing Digital Twin
simulation service, and a public post is not verified incident data or a
source of precise coordinates.

**Decision**:
- Add Bluesky search behind a backend adapter and the existing authenticated
  API boundary. Request at most 100 recent search results after a traveler
  explicitly enables Social Pulse; do not paginate or call on map movement.
- Normalize and classify in the backend, aggregate by area and topic, and
  return counts, heuristic confidence, severity, trend, and freshness only.
  Keep raw text and provider identity transient; cache aggregate responses in
  process for a short TTL only.
- Resolve the selected area using the existing geocoder. The map marker is
  the selected search center, labeled area-level; it is never presented as a
  post coordinate or exact radius filter.
- Keep social context advisory. It does not enter `ContextImpactService`,
  feasibility, safety, or automatic replanning. Provide a future interpreter
  bridge without importing Nugen or changing its pipeline.

**Consequences**:
- No database migration, raw-post persistence, second geocoder, or second
  weather/context engine is introduced.
- Provider failure and no-signal states remain explicit. Task 3 is PARTIAL
  until live provider access and the already-running API process are verified;
  the current public-search request returned HTTP 403 in this environment.
- The `/api/v1/twin` namespace remains the social-context extension point;
  Task 4's what-if preview is a separate `/api/v1/digital-twin` route.

---

## ADR-059: What-if Simulation Is Ephemeral; Only Explicit Traveler Apply Reaches Replanning

**Status**: Accepted

**Decision**: Task 4 previews capture an owned itinerary snapshot and
scenario assumptions in a bounded, in-process TTL store. The preview does
not change itinerary rows or create a revision. Applying a still-current
preview requires a separate traveler action, verifies the itinerary version,
and delegates to the existing `ReplanningService.replan_itinerary()` path.

**Why**: The simulation should help a traveler compare possible conditions
without turning a hypothetical into a decision or silently changing a saved
plan. Reusing the existing replanner preserves its ownership, validation,
versioning, locking, and revision behavior.

**Alternatives Considered**:
- Persisting scenario branches or simulation results in new database tables:
  deferred; the current workflow needs only a short-lived review session.
- Applying a preview automatically or through an AI tool: rejected; the
  traveler must explicitly approve a current preview in the UI.
- Adding a Nugen/Digital Twin runtime: out of scope. The domain intelligence
  protocol and mock are extension points only.

**Consequences**:
- Preview sessions expire after 15 minutes, are capped at 256 entries, are
  lost on process restart, and are not shared across API workers.
- No database migration is required. External weather, route, and social
  evidence remains bounded and labeled; hypothetical values are not reported
  as live context.

---

## ADR-060: Travelers Can Publish Local Experiences Directly; Photos Live in the Database

**Status**: Accepted

**Decision**: An authenticated traveler can add a local place through
`POST /api/v1/contributions/experiences` (UI: `/contribute/experience`). The
submission publishes immediately as an ordinary, searchable `Experience`
after deterministic checks only: category exists, phone looks valid, the
photo decodes as JPEG/PNG/WebP, and rule-based duplicate detection (name
similarity, distance, phone, website — no AI in the decision) finds no
strong match. An uncertain match returns `POSSIBLE_DUPLICATE` so the
traveler can confirm; a strong match returns 409 and nothing is created.
Every published place is owned by a single placeholder provider,
"LocaLens Community" (fixed id `00000000-0000-0000-0000-000000000001`), and
carries `source_type="traveler_submission"`; the contributor, their
as-submitted values and the duplicate outcome are recorded in
`traveler_experience_contributions`. Photos are validated, EXIF-stripped
(including GPS), downscaled to at most 1600 px, re-encoded to JPEG and stored
in the `media_objects` table, served by `GET /api/v1/media/{key}`.

**Why**: Travelers find genuinely local spots that no import covers, and a
moderation queue would leave those contributions invisible. Photos go in the
database because the API host's disk is wiped on restart, and the database
is the one durable store every environment already has; serving them under
`/api/v1` also lets the frontend's existing same-origin proxy deliver them
without extra configuration.

**Alternatives Considered**:
- A moderation queue before publishing: deferred; the audit table keeps
  every submission traceable, so takedown or review can be added later
  without a schema change.
- Local-filesystem or object storage for photos: filesystem storage loses
  files on restart; object storage needs new credentials and a bucket, which
  can be added later by swapping `adapters/media_storage.py`.
- Converting the contributing traveler into a provider account: rejected;
  a traveler is not the business owner.

**Consequences**:
- Community-added places start with no rating, no price and no opening
  hours. The metadata and image enrichment scripts skip them, so they never
  receive synthetic ratings/hours or a replacement photo. The UI labels them
  "Community added" and shows "Price not listed".
- Each photo adds roughly 100–500 KB to the database.
- Publishing invalidates the catalog response cache so the new place
  appears in Discover immediately. Each traveler may publish 5 places per
  hour (in-process limiter; failed attempts do not count). An
  `Idempotency-Key` header makes retries and double-clicks safe.
- Provider shop photos (`POST /api/v1/experiences/{id}/image`) use the same
  validation and database storage, with `image_source="provider_upload"`;
  replacing a photo deletes the previous stored image.
