from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass

ContributionStatus = Enum(
    "published", "rejected", "duplicate_blocked",
    name="contribution_status", native_enum=False,
)
ContributionValidationStatus = Enum(
    "passed", "failed", name="contribution_validation_status", native_enum=False,
)
ContributionDuplicateCheckStatus = Enum(
    "none", "uncertain_overridden", "blocked",
    name="contribution_duplicate_check_status", native_enum=False,
)


class TravelerExperienceContribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit/provenance record for a traveler's direct-publish submission.

    This is NOT a second catalog — the canonical, searchable entity is
    still `Experience` (see docs/DECISIONS.md ADR-060). This table exists
    only so a submission is traceable back to its contributor and its
    as-submitted values, enabling future moderation/takedown/ownership-
    claim workflows without a schema redesign.

    `traveler_id` is always derived from the authenticated session on the
    server — the API layer must never accept it from the request body
    (matches the `_PROTECTED_FIELDS` convention in
    `services/experience.py`).
    """

    __tablename__ = "traveler_experience_contributions"
    __table_args__ = (
        UniqueConstraint(
            "traveler_id", "idempotency_key", name="uq_contribution_traveler_idempotency"
        ),
    )

    traveler_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    published_experience_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="SET NULL"), nullable=True, index=True
    )

    submitted_name: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_contact_phone_raw: Mapped[str] = mapped_column(String(40), nullable=False)
    submitted_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experience_categories.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    submitted_image_object_key: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[str] = mapped_column(ContributionStatus, default="published", nullable=False)
    validation_status: Mapped[str] = mapped_column(
        ContributionValidationStatus, nullable=False
    )
    duplicate_check_status: Mapped[str] = mapped_column(
        ContributionDuplicateCheckStatus, default="none", nullable=False
    )
    duplicate_of_experience_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="SET NULL"), nullable=True
    )

    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
