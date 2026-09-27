"""Traveler direct-publish "Add a Local Experience" endpoint.

Separate from POST /experiences (provider-only, `CurrentProvider`) —
travelers are never granted access to that endpoint, and providers are
never granted access to this one. Multipart, not JSON, because an image
upload travels alongside the form fields.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.catalog_cache import invalidate_catalog_cache
from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.deps import require_traveler
from src.core.display_name import derive_display_name
from src.core.errors import ApiError
from src.core.inbound_rate_limit import SlidingWindowLimiter
from src.models.user import User
from src.schemas.contribution import ContributionCreateForm, ContributionPublishResponse, ContributionSummary
from src.schemas.experience import ExperienceDetail
from src.services.contribution import (
    DuplicateExperienceError,
    PossibleDuplicateError,
    submit_experience_contribution,
)

router = APIRouter(prefix="/contributions", tags=["contributions"])

# Single-process in-memory limiter (no external rate-limit service).
# Module-level so state survives across requests within one running API
# process. Only successful publishes count against it, so a traveler fixing
# a validation error is never locked out.
_rate_limiter = SlidingWindowLimiter(
    max_calls=get_settings().contribution_rate_limit_per_hour, window_seconds=3600.0
)


def _first_validation_message(exc: ValidationError) -> str:
    for error in exc.errors():
        message = str(error.get("msg", "")).removeprefix("Value error, ")
        if message:
            return message
    return "Please check the details and try again."


@router.post("/experiences", response_model=None, status_code=201)
async def submit_experience_contribution_route(
    user: Annotated[User, Depends(require_traveler)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    image: UploadFile,
    name: Annotated[str, Form()],
    category_id: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
    contact_phone: Annotated[str, Form()],
    place_name: Annotated[str | None, Form()] = None,
    address: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    website: Annotated[str | None, Form()] = None,
    override_duplicate_check: Annotated[bool, Form()] = False,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)] = None,
) -> JSONResponse | ContributionPublishResponse:
    if _rate_limiter.is_limited(user.id):
        raise ApiError(
            "You've shared a few experiences recently — please try again later.",
            status_code=429,
        )

    try:
        form = ContributionCreateForm(
            name=name,
            category_id=category_id,
            latitude=latitude,
            longitude=longitude,
            place_name=place_name,
            address=address,
            contact_phone=contact_phone,
            description=description,
            website=website,
            override_duplicate_check=override_duplicate_check,
        )
    except ValidationError as exc:
        raise ApiError(_first_validation_message(exc), status_code=422) from exc

    # Read at most one byte past the limit: enough to reject an oversized
    # upload without buffering all of it.
    image_bytes = await image.read(settings.media_max_upload_bytes + 1)

    try:
        result = await submit_experience_contribution(
            session,
            user,
            form,
            image_bytes,
            max_upload_bytes=settings.media_max_upload_bytes,
            max_image_dimension_px=settings.media_max_image_dimension_px,
            duplicate_radius_m=settings.contribution_duplicate_radius_m,
            idempotency_key=idempotency_key,
        )
    except DuplicateExperienceError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "DUPLICATE_EXPERIENCE",
                "existing_experience_id": exc.existing_experience_id,
                "reason": exc.reason,
                "message": "We already have this place listed.",
            },
        )
    except PossibleDuplicateError as exc:
        return JSONResponse(
            status_code=200,
            content={
                "detail": "POSSIBLE_DUPLICATE",
                "existing_experience_id": exc.existing_experience_id,
                "reason": exc.reason,
                "message": "We may already have this experience.",
            },
        )

    if not result.replayed:
        _rate_limiter.record(user.id)
        invalidate_catalog_cache()

    detail = ExperienceDetail.model_validate(result.experience)
    detail_dict = detail.model_dump(mode="json")
    detail_dict["contributor_display_name"] = derive_display_name(user)

    return ContributionPublishResponse(
        experience=detail_dict,
        contribution=ContributionSummary(id=result.contribution.id, status=result.contribution.status),
    )
