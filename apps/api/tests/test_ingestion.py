from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ingest_overture import (  # noqa: E402
    IngestionReport,
    build_candidate,
    haversine_m,
    nearest_neighborhood,
    normalize_name,
    validate_and_dedupe,
)


def _row(**overrides):
    base = {
        "id": "overture-id-1",
        "name": "Test Cafe",
        "category": "cafe",
        "confidence": 0.8,
        "operating_status": None,
        "addresses": [{"freeform": "1 Test Street", "region": "MH", "postcode": "400001"}],
        "sources": [
            {"provider": "meta", "record_id": "meta-123", "license": "CDLA-Permissive-2.0"}
        ],
        "lon": 72.8317,
        "lat": 18.9281,
    }
    base.update(overrides)
    return base


def test_normalize_name_lowercases_and_strips_punctuation() -> None:
    assert normalize_name("Costa Coffee - Fort!") == "costa coffee fort"


def test_nearest_neighborhood_finds_kala_ghoda_for_its_own_centroid() -> None:
    assert nearest_neighborhood(72.8317, 18.9281) == "Kala Ghoda"


def test_haversine_zero_distance_for_identical_points() -> None:
    assert haversine_m(72.83, 18.93, 72.83, 18.93) == 0


def test_build_candidate_maps_known_category() -> None:
    candidate = build_candidate(_row())
    assert candidate is not None
    assert candidate["category_slug"] == "cafes"
    assert candidate["source_type"] == "overture_places"
    assert candidate["source_record_id"] == "overture-id-1"
    assert candidate["source_license"] == "CDLA-Permissive-2.0"
    assert candidate["locality"] == "Kala Ghoda"


def test_build_candidate_rejects_unmapped_category() -> None:
    assert build_candidate(_row(category="real_estate_service")) is None


def test_build_candidate_rejects_invalid_coordinates() -> None:
    assert build_candidate(_row(lon=999, lat=18.9)) is None


def test_validate_and_dedupe_rejects_permanently_closed() -> None:
    report = IngestionReport()
    rows = [_row(operating_status="permanently_closed")]
    accepted = validate_and_dedupe(rows, report)
    assert accepted == []
    assert report.rejected_permanently_closed == 1


def test_validate_and_dedupe_rejects_unmapped_category() -> None:
    report = IngestionReport()
    rows = [_row(category="hospital")]
    accepted = validate_and_dedupe(rows, report)
    assert accepted == []
    assert report.rejected_unmapped_category == 1


def test_validate_and_dedupe_drops_duplicate_source_id() -> None:
    report = IngestionReport()
    rows = [_row(id="dup-1"), _row(id="dup-1")]
    accepted = validate_and_dedupe(rows, report)
    assert len(accepted) == 1
    assert report.rejected_duplicate_source_id == 1


def test_validate_and_dedupe_drops_duplicate_name_within_proximity() -> None:
    report = IngestionReport()
    rows = [
        _row(id="a", name="Same Cafe", lon=72.8317, lat=18.9281),
        _row(id="b", name="Same Cafe", lon=72.83175, lat=18.92815),  # a few meters away
    ]
    accepted = validate_and_dedupe(rows, report)
    assert len(accepted) == 1
    assert report.rejected_duplicate_name_proximity == 1


def test_validate_and_dedupe_keeps_distinct_far_apart_same_name() -> None:
    report = IngestionReport()
    rows = [
        _row(id="a", name="Costa Coffee", lon=72.8317, lat=18.9281),
        _row(id="b", name="Costa Coffee", lon=72.90, lat=19.10),  # far away — same brand, different branch
    ]
    accepted = validate_and_dedupe(rows, report)
    assert len(accepted) == 2


def test_validate_and_dedupe_preserves_provenance_fields() -> None:
    report = IngestionReport()
    accepted = validate_and_dedupe([_row()], report)
    candidate = accepted[0]
    assert candidate["source_name"] == "meta"
    assert candidate["source_confidence"] == 0.8
    assert candidate["source_version"]
    assert candidate["source_url"]
