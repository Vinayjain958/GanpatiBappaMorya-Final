"""Provenance-preserving exports for openly licensed source records."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OverturePlaceSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_record_id: str
    source_place_record_id: str | None = None
    source_name: str
    source_license: str
    source_version: str
    source_url: str
    source_confidence: float | None = None
    name: str
    overture_category: str | None = None
    operating_status: str | None = None
    latitude: float
    longitude: float
    address: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class OverturePlaceEnrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_name: str
    category_slug: str
    estimated_duration_minutes: int | None = None
    estimated_price_low: float | None = None
    estimated_price_high: float | None = None


class OverturePlaceDatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_record: OverturePlaceSourceRecord
    localens_enrichment: OverturePlaceEnrichment


class OverturePlaceDatasetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    snapshot_version: str
    is_live: bool = False
    record_count: int
    synthetic_records_included: bool = False
    attribution_note: str
    records: list[OverturePlaceDatasetRecord]


__all__ = [
    "OverturePlaceDatasetRecord",
    "OverturePlaceDatasetResponse",
    "OverturePlaceEnrichment",
    "OverturePlaceSourceRecord",
]
