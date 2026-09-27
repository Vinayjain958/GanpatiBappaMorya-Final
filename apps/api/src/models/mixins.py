"""Shared column mixins.

`ProvenanceMixin` is applied to every entity that may be derived from an
external open-data source (Location, Provider, Experience). It is a plain
mixin (columns on each table), not a separate joined table — this keeps
querying simple while still avoiding copy-pasted column definitions.
See docs/AI_CONTEXT.md INV-8 and docs/DECISIONS.md for the provenance
requirement.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProvenanceMixin:
    """Tracks where a record's facts came from, per docs/DECISIONS.md ADR-015.

    - source_type / source_name / source_record_id / source_version:
      identify the upstream dataset and the specific record within it
      (e.g. source_type="overture_places", source_name="meta",
      source_record_id="160726717984387", source_version="2026-08-19.0").
    - is_synthetic: true for LocaLens-authored demo records with no
      external source.
    - is_enriched: true when LocaLens has added derived fields (estimated
      duration, tags, etc.) on top of source facts.
    """

    source_type: Mapped[str] = mapped_column(String(40), default="synthetic", nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enriched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
