"""ContextSnapshot model (Phase 9).

Persisted, normalized record of a weather/event context fetch, kept only
for replan traceability/audit (the Phase 9 spec's "if the existing cache
abstraction is sufficient, prefer it" — TTLCache already handles the
hot-path fast-lookup case; this table exists so a replan's
ItineraryRevision.context_snapshot_reference points at something durable
even after the in-memory cache entry expires). Never stores raw provider
payloads or secrets — `payload` is the same normalized shape
WeatherContext/ExternalEvent expose.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Index

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ContextType = Enum("WEATHER", "EVENTS", name="context_snapshot_type", native_enum=False)


class ContextSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "context_snapshots"

    context_type: Mapped[str] = mapped_column(ContextType, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "lat:lng" or "lat:lng:radius"
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # LIVE | CACHED | MOCK | UNAVAILABLE
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(40), nullable=True)

    __table_args__ = (
        Index("ix_context_snapshots_type_scope", "context_type", "scope_key"),
    )


__all__ = ["ContextSnapshot", "ContextType"]
