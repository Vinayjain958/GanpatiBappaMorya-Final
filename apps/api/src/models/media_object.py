from __future__ import annotations

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MediaObject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A traveler-uploaded image, stored in the database.

    The API runs on hosts with an ephemeral filesystem (Render's free plan
    wipes local disk on every restart/spin-down), so files written to disk
    would silently disappear. Images are already validated, EXIF-stripped
    and re-encoded to a bounded JPEG by services/media_validation.py before
    they reach this table, so rows stay small. Served read-only by
    GET /api/v1/media/{object_key} (api/v1/media.py).

    `object_key` is always server-generated (e.g. "experiences/<hex>.jpg"),
    never derived from a client-supplied filename.
    """

    __tablename__ = "media_objects"

    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
