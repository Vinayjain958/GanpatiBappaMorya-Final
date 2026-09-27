from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience


class ExperienceOpeningHour(UUIDPrimaryKeyMixin, Base):
    """One open/closed window for a single day of the week.

    day_of_week: 0=Monday .. 6=Sunday (ISO-ish, deterministic and portable).
    A day can have multiple rows (e.g. split lunch/dinner windows).
    is_closed=True rows have null open/close times and mean "known closed
    that day" — distinct from simply having no row (which means unknown).
    """

    __tablename__ = "experience_opening_hours"
    __table_args__ = (
        UniqueConstraint(
            "experience_id", "day_of_week", "open_time", "close_time",
            name="uq_opening_hour_window",
        ),
    )

    experience_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    open_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"
    close_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    experience: Mapped[Experience] = relationship(back_populates="opening_hours")
