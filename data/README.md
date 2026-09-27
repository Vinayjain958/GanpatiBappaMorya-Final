# LocaLens — Data Sources & Provenance

> Documents where every record in the LocaLens catalog came from, what
> LocaLens added on top of it, and what is entirely synthetic.
> Last updated: 2026-09-22 (Phase 4).

---

## 1. Hybrid data strategy

```
OVERTURE MAPS PLACES (open, real-world POIs)
        +
LocaLens enrichment (derived, estimated — always labelled)
        +
LocaLens synthetic demo layer (fictional, always labelled)
        ↓
LocaLens experience catalog (database)
```

No record's source is misrepresented: every `Location`, `Provider`, and
`Experience` row carries provenance columns (`source_type`, `source_name`,
`source_record_id`, `source_version`, `source_license`, `source_confidence`,
`is_synthetic`, `is_enriched`) — see `apps/api/src/models/mixins.py`
(`ProvenanceMixin`).

---

## 2. Primary source: Overture Maps Places

- **Source**: [Overture Maps Foundation](https://overturemaps.org) — Places theme
- **Access method**: DuckDB `spatial`/`httpfs` extensions querying the
  public cloud Parquet store directly
  (`s3://overturemaps-us-west-2/release/<release>/theme=places/type=place/*`),
  per the official guide: https://docs.overturemaps.org/getting-data/duckdb/
- **No API key required.** A geographic bounding box is pushed down to
  Parquet row-group statistics, so only the relevant slice is scanned —
  the full global dataset (tens of millions of rows) is never downloaded.
- **Release used**: `2026-08-19.0` (the latest release available at
  ingestion time; confirmed via the bucket's `release/` prefix listing).
  This is a **downloaded snapshot**, not a live feed — re-running
  `scripts/ingest_overture.py` against a newer release will change results.
- **Geographic coverage (bounding box)**: `lon 72.75–72.98, lat 18.87–19.22`
  — spans Colaba/Fort/Churchgate/Marine Drive through Dadar/Matunga/Bandra/
  Juhu/Andheri/Lower Parel/Powai. Neighborhood labels are assigned by
  nearest-centroid distance for readability only; they do not gate any
  future ranking/eligibility logic.
- **Schema reference**: https://docs.overturemaps.org/schema/reference/places/
  (fields used: `id`, `names.primary`, `categories.primary`, `confidence`,
  `operating_status`, `addresses`, `sources`, `geometry`).
  As of this release, the Places schema has **no structured opening-hours
  field** — this is why Overture-derived experiences have
  `opening_hours_status = "unavailable"` rather than invented hours.
- **Per-record provenance**: each Overture Places record carries a
  `sources` array identifying the contributing dataset (in this ingestion,
  predominantly `provider: "meta"`) and a license
  (`CDLA-Permissive-2.0` on every record observed). LocaLens copies the
  `record_id`, `provider`/`dataset` name, and `license` into
  `source_record_id` / `source_name` / `source_license` on both the
  `Location` and `Experience` rows, and sets `attribution_required = true`
  with a generated `attribution_text`.
- **Attribution**: per
  https://docs.overturemaps.org/attribution/, Overture aggregates data
  from multiple upstream sources with their own licenses, so attribution
  is tracked per record rather than assumed uniform. The Places theme
  **does not** contain OpenStreetMap data
  (https://docs.overturemaps.org/guides/places/) — LocaLens does not
  claim OSM as a source for any Places-derived record.
- **Not used in Phase 2**: OpenStreetMap, Nominatim, Overpass, OSRM (all
  deferred to Phase 4 per `docs/ROADMAP.md`).

### What was explicitly NOT scraped

No data was collected from Google Maps, TripAdvisor, Airbnb, Zomato,
Swiggy, Yelp, Instagram, Facebook, or any other platform with unclear
scraping permissions. Overture Places was chosen specifically because it
is an openly licensed, bulk-downloadable dataset with per-record
provenance.

---

## 3. Ingestion pipeline (`apps/api/scripts/ingest_overture.py`)

```
Query Overture (bbox + category allowlist + confidence >= 0.30 + name present)
        ↓
Cap 30 raw rows per Overture category (diversity, keeps export small)
        ↓
Export raw rows -> data/raw/overture_places_mumbai_raw.json (gitignored)
        ↓
Validate: reject permanently_closed, unmapped category, bad name, bad coordinates
        ↓
Deduplicate: exact source_record_id, then normalized-name + <75m proximity
        ↓
Cap 16 accepted rows per LocaLens category (final catalog balance)
        ↓
Write data/processed/overture_experiences.json (committed — small, ~275KB)
Write data/processed/ingestion_report.json (counts at every stage)
```

Re-running `python scripts/ingest_overture.py` (from `apps/api/`, with
`pip install -r requirements-ingestion.txt`) always re-queries Overture
and deterministically overwrites the processed output — this is what
"reproducible" means here: same filters and release → same candidate set.

### Category mapping

Overture's `categories.primary` values are mapped to LocaLens's ~20-slug
taxonomy in **one place**: `apps/api/src/core/category_map.py`
(`OVERTURE_CATEGORY_MAP`). No category-translation logic exists anywhere
else in the app. Categories with no Overture equivalent in this bounding
box (`street-food`, `hidden-gems`) are populated only by the synthetic
layer — this is stated explicitly rather than forced.

Overture categories intentionally **excluded** from ingestion: real
estate, banking/finance, healthcare, legal/professional services,
schools/education, IT companies, and similar categories not relevant to
local experience discovery.

---

## 4. LocaLens enrichment (applied at seed time, `apps/api/scripts/seed.py`)

Every Overture-derived `Experience` gets `is_enriched = true` and the
following LocaLens-authored fields, each traceable to an estimate rather
than a verified fact:

| Field | Source | How it's marked |
|---|---|---|
| `short_description` / `full_description` | Deterministic template from name + category + locality | Text says "sourced from open place data" |
| `minimum_price` / `maximum_price` | Category-level estimated band (e.g. cafés ₹150–500) | `price_source="estimated"`, `is_price_estimated=true` |
| `duration_minutes` | Category-level estimate | `duration_is_estimated=true` |
| `suitability`, `tags` | Category-based defaults | — |
| `rating`, `review_count` | **Not populated** — Overture Places has no rating field in this release | `null` (never fabricated) |
| `wheelchair_accessible`, `step_free` | **Not populated** — no source data | `null` (never fabricated) |
| `opening_hours` | **Not populated** — no source field this release | `opening_hours_status="unavailable"` |

No specific factual claims (e.g. "90-minute guided tour", a star rating,
or a review count) are invented for source-derived records.

---

## 5. Synthetic demo layer (`apps/api/scripts/synthetic_data.py`)

Open POI data describes places, not bookable *experiences* — it has no
concept of guided tours, workshop capacity, or hosted activities. A
smaller, clearly labelled (`is_synthetic = true`) layer fills this gap
using controlled templates (neighborhood + category-appropriate phrase,
e.g. "Kala Ghoda Artisan Sketch Walk"), not free-form generation.

- All business/provider names are **fictional**. Any resemblance to a
  real business is coincidental.
- Deterministic (fixed random seed) — re-running the seed script produces
  the same synthetic dataset every time.
- Synthetic experiences DO get structured `ExperienceOpeningHour` rows
  (from a small set of realistic day/time presets) and DO get estimated
  price/duration — same estimation approach as the enrichment layer, also
  marked `is_price_estimated=true` / `duration_is_estimated=true`.
- No fake reviews, ratings, or "verified" claims are attached to
  synthetic records — `verification_status="curated"`, never `"verified"`.

---

## 6. Current dataset snapshot (last seed run)

| Metric | Count |
|---|---|
| Overture Places release | `2026-08-19.0` |
| Raw candidates queried (post bbox+category+confidence filter, pre-cap) | 1,557 |
| Accepted source-derived experiences (after dedup/validation/cap) | 288 |
| Synthetic experiences | 65 |
| **Total experiences** | **353** |
| Categories | 20 |
| Overture-derived providers (deduped by normalized business name) | 261 |
| Synthetic providers | 50 |
| **Total providers** | **311** |
| Locations | 353 |
| Duplicate source IDs found | 0 |

Full detail: `data/processed/ingestion_report.json`.

Re-seeding: `cd apps/api && python scripts/seed.py` (full reseed of the
catalog tables; safe to re-run).

---

## 7. What is committed vs. gitignored

- **Committed**: `apps/api/scripts/ingest_overture.py`,
  `apps/api/scripts/seed.py`, `apps/api/scripts/synthetic_data.py`,
  `apps/api/src/core/category_map.py`, `data/processed/overture_experiences.json`
  (~275KB, the curated candidate set), `data/processed/ingestion_report.json`,
  this file.
- **Gitignored** (`data/raw/*`): the full raw Overture export
  (`overture_places_mumbai_raw.json`, ~2MB) — reproducible by re-running
  the ingestion script, not committed per repository size hygiene.

---

## 8. Honesty checklist for anyone extending this pipeline

- Never mark a LocaLens-estimated field as if it came from Overture.
- Never invent a rating, review count, or accessibility fact with no source.
- Never claim "live" data — this is a downloaded snapshot pinned to a release.
- Never claim OpenStreetMap as the source of Places data (it isn't, per
  Overture's own documentation).
- Always set `is_synthetic=true` on anything with no real-world source.

---

## 9. Location services (Phase 4): OSM ecosystem, live and separate from the catalog

Phase 4 adds **live** third-party services for geocoding, nearby-POI
discovery, and routing/travel-time. These are architecturally distinct
from the Overture-derived catalog above:

- They are **not** ingested into the database and **never** become
  `Experience` rows. An Overpass POI result is a transient search result,
  shown only inside the map/location UI, never persisted as a catalog
  listing (see `docs/DECISIONS.md`, "Catalog vs. OSM POI distinction").
- They are called live, per-request, through backend adapters only — the
  browser never calls Nominatim/Overpass/OSRM directly
  (`apps/api/src/adapters/{geocoding,poi,routing}.py`).
- Every response that depends on them is honestly labelled — routing
  results carry `source: "osrm" | "haversine_estimate"`, and if
  `LOCATION_SERVICES_ENABLED=false` or a live call fails, the app falls
  back to the portable Haversine estimate or an empty result, never a
  silent fabrication.

### 9.1 Geocoding — Nominatim (OpenStreetMap)

- **Source**: [Nominatim](https://nominatim.org), OpenStreetMap's public
  geocoding service, default `NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org`.
- **Data**: © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright).
- **Usage policy compliance**
  (https://operations.osmfoundation.org/policies/nominatim/): a
  descriptive `User-Agent` is sent on every request
  (`NOMINATIM_USER_AGENT`), requests are rate-limited to at most 1/sec
  (`NOMINATIM_MIN_INTERVAL_SECONDS`) via `IntervalRateLimiter`, results
  are cached in-process for `NOMINATIM_CACHE_TTL_SECONDS` to avoid
  repeat lookups, and **no autocomplete/type-ahead querying** is
  implemented — search is explicit-submit only
  (`apps/web/hooks/useLocationSearch.ts`).
- **Used for**: forward search ("Fort Mumbai" → coordinates) and reverse
  geocoding (coordinates → place label) in the Discover location bar and
  provider experience-location picker.

### 9.2 Nearby places — Overpass API (OpenStreetMap)

- **Source**: [Overpass API](https://overpass-api.de), default
  `OVERPASS_BASE_URL=https://overpass-api.de/api/interpreter`.
- **Data**: © OpenStreetMap contributors, ODbL.
- **Usage policy compliance**: deterministic, server-built Overpass QL
  queries only (`apps/api/src/adapters/poi.py`, `_build_overpass_query()`
  — a small `POI_CATEGORY_TAGS` allowlist, never free-form user QL),
  radius capped at `OVERPASS_MAX_RADIUS_M`, rate-limited to
  `OVERPASS_MIN_INTERVAL_SECONDS`, cached for
  `OVERPASS_CACHE_TTL_SECONDS`. Overpass's public instance load-sheds
  (429/504) under fair-use pressure — the adapter surfaces this as a
  typed `AdapterRateLimitedError`/`AdapterUnavailableError` so the UI
  degrades gracefully instead of erroring the whole page.
- **Used for**: "nearby points of interest" map queries. **Results are
  informational only** — they are OSM tags rendered on the map, not
  LocaLens experiences, and carry no price/booking/provider data.

### 9.3 Routing & travel time — OSRM

- **Source**: [Project OSRM](https://project-osrm.org) public demo
  server, default `OSRM_BASE_URL=https://router.project-osrm.org`. This
  is a shared, best-effort public instance with no uptime guarantee —
  suitable for a hackathon prototype, not for production load.
- **Routing data**: derived from OpenStreetMap, © OpenStreetMap
  contributors, ODbL.
- **Usage**: rate-limited (`OSRM_MIN_INTERVAL_SECONDS`), cached
  (`OSRM_CACHE_TTL_SECONDS`), profile restricted to
  `OSRM_ALLOWED_PROFILES` (`driving`/`walking`/`cycling`), and the
  travel-time matrix is capped at `OSRM_MAX_MATRIX_DESTINATIONS` per
  request so a single discovery page load can't fan out unbounded calls.
- **Used for**: the experience detail page's "Show route" action and
  per-result travel-time enrichment on `GET /experiences`. When OSRM is
  unavailable or disabled, the app falls back to a Haversine straight-line
  distance estimate and labels it `travel_time_source: "haversine_estimate"`
  — never presented as an actual road route.

### 9.4 Map rendering — MapLibre GL JS + OpenFreeMap

- **Map library**: [MapLibre GL JS](https://maplibre.org) (`apps/web/components/common/MapSurface.tsx`)
  — open-source, no API key, replaces the Phase 1 static placeholder.
- **Map style/tiles**: [OpenFreeMap](https://openfreemap.org)
  (`tiles.openfreemap.org/styles/liberty`, configurable via
  `NEXT_PUBLIC_MAP_STYLE_URL`) — a free, no-API-key vector tile and style
  host built on OpenStreetMap data. Attribution is rendered in-map via
  MapLibre's `AttributionControl` (`apps/web/lib/config/map.ts`).
- Experience markers are drawn from a clustered GeoJSON source (never one
  DOM marker per result) built from already-fetched catalog data — the
  map does not issue its own separate data queries beyond style/tiles.

### 9.5 Summary: source vs. renderer vs. tiles vs. geocoding vs. routing

| Concern | Provider | Key required | Notes |
|---|---|---|---|
| Catalog data source | Overture Maps Places | No | Downloaded snapshot, see §2 |
| Map rendering library | MapLibre GL JS | No | Open-source JS library, not a data source |
| Map tiles/style | OpenFreeMap | No | Vector tiles, built on OSM data |
| Geocoding (search) | Nominatim (OSM) | No | Rate-limited, cached, no autocomplete |
| Nearby POIs | Overpass API (OSM) | No | Informational only, never becomes catalog data |
| Routing / travel time | OSRM public demo | No | Best-effort; falls back to Haversine estimate |

---

## 10. Additive expanded Overture catalog snapshot

`data/processed/overture_catalog_addon.json` is an additive, normalized
snapshot extracted from the supplied project archive's development database.
The export includes only active rows with `source_type="overture_places"`,
`is_synthetic=false`, valid coordinates, and per-record source ID, provider,
license, version, and URL. It contains 14,875 Overture-derived records across
the archived `2026-08-19.0` and `2026-09-23.1` releases. The original
`overture_experiences.json` snapshot is retained unchanged.

The additive import into the local development database is recorded in
`data/processed/catalog_addon_import_report.json`: 14,587 records were added,
288 were already present, and a second dry-run found no new rows. The report
also records the verified pre-import database backup and post-import row counts.

The archive's database also contained synthetic rows, a traveler-submitted
row, and account/trip data. None of those records were exported. The archived
normalized catalog did not retain Overture's original primary category or
operating status for every place; the expanded source-data endpoint leaves
those fields null. LocaLens category mapping and any price/duration estimates
remain in the separate `localens_enrichment` object. Missing prices, ratings,
reviews, opening hours, and availability are not filled in.

`GET /api/v1/experiences/source-data/overture/catalog` serves this archived
snapshot. To add catalog rows to the local database, run
`python scripts/import_overture_catalog_addon.py` from `apps/api/` for a dry
run, then add `--apply`. The importer only inserts source IDs not already
present; it does not reset or update existing catalog, account, itinerary, or
safety rows. Re-running it is safe.
