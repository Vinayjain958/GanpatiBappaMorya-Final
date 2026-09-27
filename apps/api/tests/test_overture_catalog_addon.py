from __future__ import annotations


def test_expanded_overture_catalog_is_provenance_labeled_and_excludes_demo_rows(client) -> None:
    response = client.get("/api/v1/experiences/source-data/overture/catalog")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["is_live"] is False
    assert payload["synthetic_records_included"] is False
    assert payload["record_count"] == 14875
    assert len(payload["records"]) == payload["record_count"]
    assert "full raw Overture dump" in payload["attribution_note"]

    record = payload["records"][0]
    source = record["source_record"]
    enrichment = record["localens_enrichment"]
    assert source["source_record_id"]
    assert source["source_name"]
    assert source["source_license"]
    assert source["source_version"]
    assert source["source_url"]
    assert source["overture_category"] is None
    assert source["operating_status"] is None
    assert -90 <= source["latitude"] <= 90
    assert -180 <= source["longitude"] <= 180
    assert enrichment["category_slug"]
