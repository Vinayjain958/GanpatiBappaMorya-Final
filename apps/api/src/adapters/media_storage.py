"""Storage for traveler-uploaded experience photos.

Images live in the `media_objects` table rather than on local disk: the API
is deployed to hosts whose filesystem is wiped on restart, and the database
is the one durable store every environment already has. The row is written
inside the caller's session, so it commits (or rolls back) atomically with
the Experience that references it — a failed publish never leaves an
orphaned upload behind.

Callers get back a host-relative URL under the API's own /api/v1 prefix.
The frontend proxies /api/v1/* same-origin, so the URL works unchanged in
local dev and in production.
"""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.media_object import MediaObject

MEDIA_URL_PREFIX = "/api/v1/media"

_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$")


def is_safe_object_key(key: str) -> bool:
    return bool(_SAFE_KEY_RE.match(key)) and ".." not in key.split("/")


def media_url_for(key: str) -> str:
    return f"{MEDIA_URL_PREFIX}/{key}"


class DatabaseMediaStorage:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def save(self, data: bytes, key: str, content_type: str) -> str:
        """Stage `data` under `key` in the current session; returns its URL.

        Nothing is committed here — the caller's commit persists it.
        """
        if not is_safe_object_key(key):
            raise ValueError(f"Refusing unsafe media storage key: {key!r}")
        self._session.add(
            MediaObject(object_key=key, content_type=content_type, size_bytes=len(data), data=data)
        )
        return media_url_for(key)

    async def delete_url(self, url: str | None) -> None:
        """Stage deletion of a previously stored image, given its URL.
        URLs that aren't ours (Wikimedia, category art) are ignored."""
        prefix = f"{MEDIA_URL_PREFIX}/"
        if not url or not url.startswith(prefix):
            return
        await self._session.execute(
            delete(MediaObject).where(MediaObject.object_key == url.removeprefix(prefix))
        )
