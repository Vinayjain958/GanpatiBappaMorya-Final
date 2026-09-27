# apps/api/

FastAPI backend for LocaLens.

**Phase**: 6 — Semantic Retrieval + Constraint / Feasibility Engine

## Stack

- Python 3.12+
- FastAPI, Pydantic v2 / pydantic-settings
- Uvicorn (ASGI server)
- SQLAlchemy 2.0 (async) + Alembic — SQLite (dev) / PostgreSQL+asyncpg (production-compatible)
- PyJWT (HS256) + pwdlib[argon2] for authentication
- httpx (shared async client) — Nominatim (geocoding), Overpass API (nearby POIs), OSRM (routing/
  travel-time); all rate-limited, TTL-cached, mock-fallback via `LOCATION_SERVICES_ENABLED`
- `google-genai` — Gemini text (`gemini-3.8-flash`, structured `TravelerContext` extraction),
  Gemini Live (`gemini-3.8-live`, ephemeral tokens), and Gemini embeddings (`gemini-embedding-2`,
  Phase 6, **NOT VERIFIED live — no API key available**); mock-fallback via `GEMINI_ENABLED`
- `tzdata` — required for `zoneinfo` timezone-aware opening-hours checks (Phase 6) on platforms
  without system tzdata (e.g. this Windows dev environment; also relevant to minimal Linux images)
- DuckDB (ingestion tooling only, not a runtime dependency — see `requirements-ingestion.txt`)

Further domain modules (ranking, composer, etc.) are introduced in later phases — see
`docs/ROADMAP.md`.

## Structure

```
apps/api/
├── src/
│   ├── adapters/        ← geocoding.py (Nominatim), routing.py (OSRM), poi.py (Overpass),
│   │                        ai.py (Gemini text + Live tokens), embedding.py (Gemini/Mock
│   │                        embeddings, Phase 6), errors.py (typed AdapterError hierarchy)
│   │                        + mock implementations for all
│   ├── api/v1/           ← Versioned API routes: health, auth, categories, providers,
│   │                        experiences (incl. semantic-search), availability, location,
│   │                        conversation, feasibility (Phase 6)
│   ├── core/             ← Config, db engine, app factory, category taxonomy, errors,
│   │                        startup checks, security.py (JWT/Argon2), cookies.py, deps.py
│   │                        (get_current_user/require_role/get_current_provider),
│   │                        http_client.py, cache.py (TTLCache), rate_limit.py
│   │                        (IntervalRateLimiter), geo.py (Haversine), vector_math.py (cosine
│   │                        similarity, Phase 6), feasibility_reasons.py (reason-code enum,
│   │                        Phase 6), location.py (location adapter DI), ai.py (AI adapter DI),
│   │                        embedding.py (embedding adapter DI, Phase 6)
│   ├── models/           ← SQLAlchemy models: User, Traveler, Provider, ExperienceCategory,
│   │                        Location, Experience, ExperienceOpeningHour, AuthSession,
│   │                        ExperienceAvailability, ConversationSession, ConversationMessage,
│   │                        ExperienceEmbedding (Phase 6) + provenance mixin
│   ├── repositories/     ← Data-access layer (route handlers stay thin); embedding_repository.py
│   │                        (Phase 6 — dialect-aware: JSON on SQLite, pgvector query on Postgres)
│   ├── schemas/          ← Pydantic request/response schemas, conversation.py (TravelerContext,
│   │                        search_experiences/check_feasibility tool args/result),
│   │                        feasibility.py + semantic_search.py (Phase 6)
│   ├── services/         ← auth.py, experience.py, discovery.py (deterministic relevance
│   │                        scoring — not ML), conversation.py (text-turn orchestration),
│   │                        ai_tools.py (search_experiences + check_feasibility — the two
│   │                        Gemini tools), embedding_text.py, semantic_retrieval.py,
│   │                        feasibility.py, discovery_pipeline.py (Phase 6)
│   └── main.py           ← ASGI entry point
├── scripts/
│   ├── ingest_overture.py  ← Overture Maps Places ingestion (Mumbai bbox)
│   ├── synthetic_data.py   ← Deterministic synthetic provider/experience generator
│   ├── seed.py              ← Populates the catalog (Overture + synthetic only — see below)
│   ├── create_admin.py       ← Env-driven ADMIN account creation (never via the API)
│   └── index_embeddings.py   ← Idempotent ExperienceEmbedding backfill/refresh (Phase 6)
├── alembic/              ← Async migrations
├── tests/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── requirements-ingestion.txt
```

## Authentication at a glance

- **Access token**: short-lived JWT (~15 min), returned in the JSON body, meant to be held by
  the client only in memory — never persisted.
- **Refresh token**: longer-lived JWT (~7 days), set only as an HttpOnly cookie, rotated on
  every `/auth/refresh` call; reuse of an already-rotated token revokes every session for that
  user. See `docs/DECISIONS.md` ADR-019/ADR-020.
- **Ownership**: `provider_id` is always derived from the authenticated user server-side —
  never accepted from a request body. See ADR-021.
- **Provider lineages**: catalog-imported (Overture) and synthetic demo providers have no
  `user_id` and cannot log in; only providers created via `/auth/register` can.
- `scripts/seed.py` reseeds **only** Overture/synthetic rows (`source_type in
  ("overture_places", "synthetic")`) — registered accounts and their experiences/availability
  are never touched by a reseed.

## Local development

```bash
cd apps/api
python -m venv .venv
./.venv/Scripts/activate       # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements-dev.txt

alembic upgrade head           # create/update the local SQLite database
python scripts/seed.py         # populate categories/providers/locations/experiences

uvicorn src.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/api/v1/health`
Experience catalog: `GET http://localhost:8000/api/v1/experiences` (supports `q`, `category`,
`min_price`/`max_price`, `min_duration`/`max_duration`, `lat`/`lng`/`radius_km`, `sort`)
Location services: `GET http://localhost:8000/api/v1/location/search?q=Fort+Mumbai`
Register an account: `POST http://localhost:8000/api/v1/auth/register`

Set `LOCATION_SERVICES_ENABLED=false` in `.env` to force Nominatim/Overpass/OSRM to fall back to
mock adapters (e.g. offline dev) — the catalog and radius search still work; only geocoding/
nearby-POI/routing degrade to empty/estimated results.

Conversational discovery: `POST http://localhost:8000/api/v1/conversations` then
`POST .../{id}/messages` with `{"message": "cheap local food near Fort"}`. Set a real
`GEMINI_API_KEY` in `.env` for real extraction; without one, `MockAIAdapter` still returns a
usable (if less nuanced) `TravelerContext` via deterministic keyword extraction. Voice
(`POST /auth/live-token`) always returns 503 without a real key — it never fakes a connection.

To create a local ADMIN account (never possible via the public API), set
`ADMIN_SEED_EMAIL`/`ADMIN_SEED_PASSWORD` in `.env`, then:

```bash
python scripts/create_admin.py
```

### Semantic search + feasibility (Phase 6)

Backfill `ExperienceEmbedding` rows before semantic search will return
anything (without embeddings, retrieval falls back to keyword search):

```bash
python scripts/index_embeddings.py            # embeds any missing/stale experiences
python scripts/index_embeddings.py --dry-run  # preview without writing
python scripts/index_embeddings.py --force    # re-embed everything
```

Then: `POST http://localhost:8000/api/v1/experiences/semantic-search` with
`{"query": "cheap local food near Fort", "constraints": {"budget_max": 500}}`
(requires auth). Only feasibility-verified candidates are ever returned in
`items` — see `retrieval_mode`, `feasible_count`, `excluded_count`, and
`excluded_summary` in the response for the full picture.

`POST http://localhost:8000/api/v1/feasibility/check` with
`{"experience_id": "...", "constraints": {"budget_max": 500}}` returns a
standalone tri-state verdict (FEASIBLE/INFEASIBLE/UNKNOWN) for one
experience — 100% deterministic, no Gemini call on this path.

Without a real `GEMINI_API_KEY`, `MockEmbeddingAdapter` (deterministic,
not random) is used automatically — semantic search still works, just
without real semantic understanding.

### Re-running open-data ingestion

Optional — `data/processed/overture_experiences.json` is already committed,
so `scripts/seed.py` works without this. To re-query Overture directly
(requires network access):

```bash
pip install -r requirements-ingestion.txt
python scripts/ingest_overture.py
```

See `data/README.md` for the full source/licensing/attribution documentation.

## Checks

```bash
python -m pytest
python -m ruff check src scripts tests
python -m mypy src            # scripts/ has relaxed strictness — see pyproject.toml
```

## Environment

Configuration is read from the repo-root `.env` (see `.env.example`).
The app starts even when optional credentials (Gemini, OpenWeather,
Ticketmaster, MapTiler, Supabase) are absent — dependent adapters fall
back to mock implementations and a warning is logged at startup.
`DATABASE_URL` defaults to local SQLite; switching to
`postgresql+asyncpg://...` is the only change needed for PostgreSQL.

`JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET` fall back to insecure dev-only
defaults locally; `validate_startup()` refuses to boot in production with
those defaults (or with both secrets equal).
