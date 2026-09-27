from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.experience import Experience


class ExperienceCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """LocaLens internal category taxonomy.

    Separate from Overture's `categories`/`taxonomy` fields — the mapping
    from Overture basic_category values to these slugs lives in
    scripts/ingest_overture.py (CATEGORY_MAP), not scattered across the app.
    """

    __tablename__ = "experience_categories"

    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    experiences: Mapped[list[Experience]] = relationship(back_populates="category")
