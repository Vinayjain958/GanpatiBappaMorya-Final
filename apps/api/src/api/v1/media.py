"""Public, read-only delivery of traveler-uploaded experience photos.

Object keys are random and immutable (a re-upload always gets a new key),
so responses are cached aggressively by browsers and CDNs.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.media_storage import is_safe_object_key
from src.core.db import get_session
from src.core.errors import ApiError
from src.models.media_object import MediaObject

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{object_key:path}")
async def get_media(
    object_key: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    if not is_safe_object_key(object_key):
        raise ApiError("Media not found.", status_code=404)

    media = (
        await session.execute(select(MediaObject).where(MediaObject.object_key == object_key))
    ).scalar_one_or_none()
    if media is None:
        raise ApiError("Media not found.", status_code=404)

    return Response(
        content=media.data,
        media_type=media.content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
