from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai import AIAdapter
from src.adapters.errors import AdapterError, AdapterRateLimitedError, AdapterUnavailableError
from src.core.ai import get_ai_adapter
from src.core.config import Settings, get_settings
from src.core.cookies import clear_refresh_cookie, set_refresh_cookie
from src.core.db import get_session
from src.core.deps import CurrentUser, require_traveler
from src.core.errors import ApiError
from src.models.provider import Provider
from src.models.traveler import Traveler
from src.models.user import User
from src.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    ProviderProfilePublic,
    RegisterRequest,
    TravelerProfilePublic,
    UserPublic,
)
from src.schemas.conversation import LiveTokenResponse
from src.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_response(
    settings: Settings,
    access_token: str,
    user: User,
    traveler: Traveler | None = None,
    provider: Provider | None = None,
) -> AuthResponse:
    return AuthResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_expires_minutes * 60,
        user=UserPublic.model_validate(user),
        traveler=TravelerProfilePublic.model_validate(traveler) if traveler else None,
        provider=ProviderProfilePublic.model_validate(provider) if provider else None,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    result = await auth_service.register_user(session, payload)
    tokens = await auth_service.issue_token_pair(
        session, settings, result.user, user_agent=request.headers.get("user-agent")
    )
    set_refresh_cookie(response, settings, tokens.refresh.token, tokens.refresh.expires_at)
    return _build_auth_response(
        settings, tokens.access.token, result.user, result.traveler, result.provider
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    user = await auth_service.authenticate_user(session, payload.email, payload.password)
    tokens = await auth_service.issue_token_pair(
        session, settings, user, user_agent=request.headers.get("user-agent")
    )
    traveler = user.traveler
    provider = await auth_service.load_provider_profile(session, user.id)
    set_refresh_cookie(response, settings, tokens.refresh.token, tokens.refresh.expires_at)
    return _build_auth_response(settings, tokens.access.token, user, traveler, provider)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    raw_refresh_token = request.cookies.get(settings.effective_refresh_cookie_name)
    if not raw_refresh_token:
        raise ApiError("Not authenticated", status_code=401)

    user, tokens = await auth_service.rotate_refresh_token(
        session, settings, raw_refresh_token, user_agent=request.headers.get("user-agent")
    )
    traveler = user.traveler
    provider = await auth_service.load_provider_profile(session, user.id)
    set_refresh_cookie(response, settings, tokens.refresh.token, tokens.refresh.expires_at)
    return _build_auth_response(settings, tokens.access.token, user, traveler, provider)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    raw_refresh_token = request.cookies.get(settings.effective_refresh_cookie_name)
    await auth_service.logout_session(session, settings, raw_refresh_token)
    clear_refresh_cookie(response, settings)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    traveler = user.traveler
    provider = await auth_service.load_provider_profile(session, user.id)
    return MeResponse(
        user=UserPublic.model_validate(user),
        traveler=TravelerProfilePublic.model_validate(traveler) if traveler else None,
        provider=ProviderProfilePublic.model_validate(provider) if provider else None,
    )


@router.post("/live-token", response_model=LiveTokenResponse)
async def issue_live_token(
    user: Annotated[User, Depends(require_traveler)],
    ai: Annotated[AIAdapter, Depends(get_ai_adapter)],
) -> LiveTokenResponse:
    """Issues a short-lived Gemini Live ephemeral token (Phase 5).

    Traveler-only — conversational voice discovery is a traveler-facing
    surface, not provider/admin tooling (docs/DECISIONS.md ADR-034). The
    master GEMINI_API_KEY never leaves the backend; only this ephemeral,
    scope-locked token is returned. Never logged, never persisted.
    """
    try:
        result = await ai.issue_live_token()
    except AdapterError as exc:
        if isinstance(exc, AdapterRateLimitedError):
            raise ApiError("Voice is temporarily rate-limited. Please try again shortly.", 503) from exc
        if isinstance(exc, AdapterUnavailableError):
            raise ApiError("Live voice is not available right now.", 503) from exc
        raise ApiError("Unexpected AI service error.", 503) from exc

    return LiveTokenResponse(
        token=result.token,
        expire_time=result.expire_time,
        new_session_expire_time=result.new_session_expire_time,
        model=result.model,
    )
