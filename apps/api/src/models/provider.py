from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience

ProviderVerificationStatus = Enum(
    "unverified", "catalog_imported", "verified",
    name="provider_verification_status", native_enum=False,
)


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, ProvenanceMixin, Base):
    """Catalog ownership entity for an experience.

    Provider account creation/auth belongs to Phase 3 — user_id stays
    nullable until then. Providers derived from an Overture place are
    NOT automatically real LocaLens business accounts: their
    verification_status is "catalog_imported", never "verified", and
    ProvenanceMixin.source_type records exactly where they came from.
    """

    __tablename__ = "providers"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        ProviderVerificationStatus, default="unverified", nullable=False
    )
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    experiences: Mapped[list[Experience]] = relationship(back_populates="provider")
