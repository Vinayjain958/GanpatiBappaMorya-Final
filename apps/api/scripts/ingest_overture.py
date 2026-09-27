"""Overture Maps Places ingestion for the Mumbai prototype dataset.

Queries the official Overture Places theme directly from its public cloud
parquet store (no API key, no full-dataset download — a geographic bounding
box is pushed down to the Parquet row-group statistics) using DuckDB's
spatial/httpfs extensions, per the official guide:
https://docs.overturemaps.org/getting-data/duckdb/

Pipeline (see docs/ARCHITECTURE.md and data/README.md for the full story):
  1. Query Mumbai bbox, category allowlist, and basic quality thresholds
  2. Cap per-category volume for diversity, export raw rows -> data/raw/ (gitignored)
  3. Normalize names/categories/addresses; assign a neighborhood by nearest-centroid
  4. Deduplicate (source_record_id, normalized-name + proximity)
  5. Validate (coordinates, name, mapped category, not permanently closed)
  6. Enrich with LocaLens-derived fields (clearly marked as enriched/estimated)
  7. Write accepted candidates + an ingestion report -> data/processed/

Run:
    cd apps/api
    pip install -r requirements-ingestion.txt
    python scripts/ingest_overture.py

Re-running is safe: it always re-queries Overture and overwrites the
processed output deterministically (same filters -> same candidate set,
modulo upstream data changes).
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.category_map import OVERTURE_CATEGORY_MAP  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW_DIR = REPO_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Overture release queried. Update when re-ingesting against a newer
# release; keep the previous value recorded in data/README.md history.
OVERTURE_RELEASE = "2026-08-19.0"
OVERTURE_S3_BASE = "s3://overturemaps-us-west-2/release"
OVERTURE_PLACES_URL = f"{OVERTURE_S3_BASE}/{OVERTURE_RELEASE}/theme=places/type=place/*"
SOURCE_URL_REFERENCE = "https://docs.overturemaps.org/guides/places/"

# Mumbai prototype coverage bounding box (South Mumbai through Powai/Andheri/Juhu).
BBOX = {"min_lon": 72.75, "max_lon": 72.98, "min_lat": 18.87, "max_lat": 19.22}

# Neighborhood centroids used only to assign a human-readable `locality`
# label to ingested points (nearest-centroid) — not used for any ranking
# or eligibility logic.
NEIGHBORHOODS: dict[str, tuple[float, float]] = {
    "Fort": (72.8356, 18.9346),
    "Kala Ghoda": (72.8317, 18.9281),
    "Colaba": (72.8147, 18.9067),
    "Churchgate": (72.8267, 18.9354),
    "Marine Drive": (72.8235, 18.9440),
    "Dadar": (72.8438, 19.0176),
    "Matunga": (72.8570, 19.0270),
    "Bandra": (72.8295, 19.0596),
    "Juhu": (72.8263, 19.1075),
    "Andheri": (72.8468, 19.1197),
    "Lower Parel": (72.8300, 18.9960),
    "Powai": (72.9060, 19.1176),
}

MIN_CONFIDENCE = 0.30
MAX_PER_CATEGORY = 30  # caps raw export volume; final target trimming happens later
TARGET_PER_CATEGORY = 16  # final catalog cap per LocaLens category, highest-confidence first
NAME_MIN_LENGTH = 3

# Estimated duration in minutes per LocaLens category. These are LocaLens
# enrichment defaults (is_enriched=True, duration_is_estimated=True) — not
# sourced facts. See docs/PROJECT_STATE.md for rationale.
ESTIMATED_DURATION_MINUTES = {
    "food-drink": 60, "street-food": 45, "cafes": 45, "culture-heritage": 60,
    "art-galleries": 50, "museums": 75, "workshops": 100, "crafts": 90,
    "shopping-markets": 60, "outdoors": 60, "adventure": 120, "photography": 60,
    "family": 90, "nightlife": 90, "music": 90, "community": 45,
    "hidden-gems": 45, "wellness": 75, "entertainment": 120, "local-experiences": 120,
}

# Estimated price band (INR) per category. Marked is_price_estimated=True,
# price_source="estimated" — never presented as a verified source price.
ESTIMATED_PRICE_RANGE = {
    "food-drink": (200, 900), "street-food": (50, 250), "cafes": (150, 500),
    "culture-heritage": (0, 200), "art-galleries": (0, 400), "museums": (50, 500),
    "workshops": (500, 2000), "crafts": (300, 1500), "shopping-markets": (0, 1000),
    "outdoors": (0, 100), "adventure": (500, 3000), "photography": (0, 300),
    "family": (100, 800), "nightlife": (400, 1500), "music": (200, 1200),
    "community": (0, 100), "hidden-gems": (0, 500), "wellness": (300, 2000),
    "entertainment": (150, 800), "local-experiences": (300, 1500),
}


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_neighborhood(lon: float, lat: float) -> str:
    return min(NEIGHBORHOODS, key=lambda name: haversine_m(lon, lat, *NEIGHBORHOODS[name]))


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


@dataclass
class IngestionReport:
    overture_release: str = OVERTURE_RELEASE
    bbox: dict = field(default_factory=lambda: dict(BBOX))
    queried_at: str = ""
    raw_candidate_count: int = 0
    rejected_invalid_geometry: int = 0
    rejected_bad_name: int = 0
    rejected_unmapped_category: int = 0
    rejected_permanently_closed: int = 0
    rejected_duplicate_source_id: int = 0
    rejected_duplicate_name_proximity: int = 0
    rejected_over_category_cap: int = 0
    accepted_count: int = 0
    accepted_by_category: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__


def query_overture_places() -> list[dict]:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL spatial; INSTALL httpfs; LOAD spatial; LOAD httpfs;")
    con.execute("SET s3_region='us-west-2';")

    category_list = ",".join(f"'{c}'" for c in OVERTURE_CATEGORY_MAP)

    query = f"""
    WITH filtered AS (
        SELECT
            id,
            names.primary AS name,
            categories.primary AS category,
            confidence,
            operating_status,
            addresses,
            sources,
            ST_X(geometry) AS lon,
            ST_Y(geometry) AS lat,
            ROW_NUMBER() OVER (
                PARTITION BY categories.primary ORDER BY confidence DESC
            ) AS rank_in_category
        FROM read_parquet('{OVERTURE_PLACES_URL}', filename=true, hive_partitioning=1)
        WHERE bbox.xmin BETWEEN {BBOX['min_lon']} AND {BBOX['max_lon']}
          AND bbox.ymin BETWEEN {BBOX['min_lat']} AND {BBOX['max_lat']}
          AND categories.primary IN ({category_list})
          AND names.primary IS NOT NULL
          AND length(names.primary) >= {NAME_MIN_LENGTH}
          AND confidence >= {MIN_CONFIDENCE}
    )
    SELECT id, name, category, confidence, operating_status, addresses, sources, lon, lat
    FROM filtered
    WHERE rank_in_category <= {MAX_PER_CATEGORY}
    ORDER BY category, confidence DESC
    """

    columns = [
        "id", "name", "category", "confidence", "operating_status",
        "addresses", "sources", "lon", "lat",
    ]
    rows = con.execute(query).fetchall()
    return [dict(zip(columns, row, strict=True)) for row in rows]


def extract_provenance(row: dict) -> dict:
    """Pick the most informative entry from Overture's `sources` array.

    Overture Places records list one or more source entries (e.g. a data
    provider like "meta" plus an "Overture"/confidence-calculation entry).
    We prefer the provider entry with a record_id for attribution.
    """
    sources = row.get("sources") or []
    provider_entry = next((s for s in sources if s.get("record_id")), None)
    entry = provider_entry or (sources[0] if sources else {})
    return {
        "source_name": entry.get("provider") or entry.get("dataset"),
        "source_record_id": entry.get("record_id"),
        "source_license": entry.get("license"),
        "source_update_time": entry.get("update_time"),
    }


def build_candidate(row: dict) -> dict | None:
    category_slug = OVERTURE_CATEGORY_MAP.get(row["category"])
    if not category_slug:
        return None

    lon, lat = row["lon"], row["lat"]
    if lon is None or lat is None or not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
        return None

    addresses = row.get("addresses") or []
    address = addresses[0] if addresses else {}
    provenance = extract_provenance(row)
    locality = nearest_neighborhood(lon, lat)

    duration = ESTIMATED_DURATION_MINUTES.get(category_slug, 60)
    price_low, price_high = ESTIMATED_PRICE_RANGE.get(category_slug, (0, 500))

    return {
        "source_type": "overture_places",
        "source_record_id": row["id"],
        "source_name": provenance["source_name"] or "overture",
        "source_license": provenance["source_license"] or "unknown",
        "source_version": OVERTURE_RELEASE,
        "source_url": SOURCE_URL_REFERENCE,
        "source_confidence": row["confidence"],
        "source_place_record_id": provenance["source_record_id"],
        "name": row["name"].strip(),
        "normalized_name": normalize_name(row["name"]),
        "category_slug": category_slug,
        "overture_category": row["category"],
        "operating_status": row["operating_status"],
        "latitude": lat,
        "longitude": lon,
        "address": address.get("freeform"),
        "locality": locality,
        "city": "Mumbai",
        "state": address.get("region") or "MH",
        "postal_code": address.get("postcode"),
        "country": "India",
        "estimated_duration_minutes": duration,
        "estimated_price_low": price_low,
        "estimated_price_high": price_high,
    }


def validate_and_dedupe(rows: list[dict], report: IngestionReport) -> list[dict]:
    report.raw_candidate_count = len(rows)
    seen_source_ids: set[str] = set()
    seen_name_points: list[tuple[str, float, float]] = []
    accepted: list[dict] = []

    for row in rows:
        if row["operating_status"] == "permanently_closed":
            report.rejected_permanently_closed += 1
            continue

        candidate = build_candidate(row)
        if candidate is None:
            report.rejected_unmapped_category += 1
            continue

        if not candidate["name"] or len(candidate["name"]) < NAME_MIN_LENGTH:
            report.rejected_bad_name += 1
            continue

        if candidate["source_record_id"] in seen_source_ids:
            report.rejected_duplicate_source_id += 1
            continue

        is_dupe = False
        for name, lon, lat in seen_name_points:
            if name == candidate["normalized_name"] and haversine_m(
                lon, lat, candidate["longitude"], candidate["latitude"]
            ) < 75:
                is_dupe = True
                break
        if is_dupe:
            report.rejected_duplicate_name_proximity += 1
            continue

        seen_source_ids.add(candidate["source_record_id"])
        seen_name_points.append(
            (candidate["normalized_name"], candidate["longitude"], candidate["latitude"])
        )
        accepted.append(candidate)

    report.rejected_over_category_cap = 0
    grouped: dict[str, list[dict]] = {}
    for candidate in accepted:
        grouped.setdefault(candidate["category_slug"], []).append(candidate)

    trimmed: list[dict] = []
    for group in grouped.values():
        group.sort(key=lambda c: c["source_confidence"], reverse=True)
        trimmed.extend(group[:TARGET_PER_CATEGORY])
        report.rejected_over_category_cap += max(0, len(group) - TARGET_PER_CATEGORY)

    report.accepted_count = len(trimmed)
    by_category: dict[str, int] = {}
    for candidate in trimmed:
        by_category[candidate["category_slug"]] = by_category.get(candidate["category_slug"], 0) + 1
    report.accepted_by_category = by_category
    return trimmed


def main() -> None:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    report = IngestionReport(queried_at=datetime.now(UTC).isoformat())

    print(f"Querying Overture Places release {OVERTURE_RELEASE} for Mumbai bbox {BBOX} ...")
    raw_rows = query_overture_places()
    print(f"Raw rows returned (post row-limit, pre-validation): {len(raw_rows)}")

    (DATA_RAW_DIR / "overture_places_mumbai_raw.json").write_text(
        json.dumps(raw_rows, default=str, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    accepted = validate_and_dedupe(raw_rows, report)
    print(f"Accepted candidates: {len(accepted)}")

    (DATA_PROCESSED_DIR / "overture_experiences.json").write_text(
        json.dumps(accepted, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_PROCESSED_DIR / "ingestion_report.json").write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(report.as_dict(), indent=2))


if __name__ == "__main__":
    main()
