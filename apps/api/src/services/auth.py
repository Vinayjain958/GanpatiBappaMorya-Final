"""Auth orchestration: registration, login, refresh rotation, logout.

Keeps route handlers thin (src/api/v1/auth.py) and keeps every
security-sensitive decision — password verification, token issuance,
session revocation, reuse detection — in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import ApiError
from src.core.security import (
    IssuedToken,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from src.models.auth_session import AuthSession
from src.models.provider import Provider
from src.models.traveler import Traveler
from src.models.user import User
from src.repositories.auth_session_repository import AuthSessionRepository
from src.repositories.provider_repository import ProviderRepository
from src.repositories.user_repository import UserRepository
from src.schemas.auth import RegisterRequest

_GENERIC_AUTH_ERROR = "Invalid email or password."


@dataclass
class RegistrationResult:
    user: User
    traveler: Traveler | None
    provider: Provider | None


@dataclass
class TokenIssue:
    access: IssuedToken
    refresh: IssuedToken


async def register_user(session: AsyncSession, payload: RegisterRequest) -> RegistrationResult:
    user_repo = UserRepository(session)
    if await user_repo.get_by_email(payload.email) is not None:
        raise ApiError("An account with this email already exists", status_code=409)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    user_repo.add(user)
    await session.flush()  # assign user.id for the profile FK

    traveler: Traveler | None = None
    provider: Provider | None = None

    if payload.role == "traveler":
        traveler = Traveler(user_id=user.id, traveler_type=payload.traveler_type)
        session.add(traveler)
    else:
        assert payload.business_name is not None  # enforced by RegisterRequest validator
        provider = Provider(
            user_id=user.id,
            business_name=payload.business_name,
            description=payload.description,
            provider_type=payload.provider_type,
            verification_status="unverified",
            source_type="registered",
            is_synthetic=False,
            is_enriched=False,
        )
        session.add(provider)

    await session.commit()
    await session.refresh(user)
    return RegistrationResult(user=user, traveler=traveler, provider=provider)


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await UserRepository(session).get_by_email(email)
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise ApiError(_GENERIC_AUTH_ERROR, status_code=401)
    if not user.is_active:
        raise ApiError(_GENERIC_AUTH_ERROR, status_code=401)
    return user


async def issue_token_pair(
    session: AsyncSession, settings: Settings, user: User, *, user_agent: str | None
) -> TokenIssue:
    access = create_access_token(settings, user.id)
    refresh = create_refresh_token(settings, user.id)

    session_row = AuthSession(
        user_id=user.id,
        jti=refresh.jti,
        token_hash=hash_refresh_token(refresh.token),
        issued_at=datetime.now(UTC),
        expires_at=refresh.expires_at,
        user_agent=user_agent,
    )
    session.add(session_row)
    await session.commit()

    return TokenIssue(access=access, refresh=refresh)


async def rotate_refresh_token(
    session: AsyncSession, settings: Settings, raw_refresh_token: str, *, user_agent: str | None
) -> tuple[User, TokenIssue]:
    try:
        claims = decode_refresh_token(settings, raw_refresh_token)
    except TokenError as exc:
        raise ApiError("Session expired or invalid — please log in again.", status_code=401) from exc

    session_repo = AuthSessionRepository(session)
    existing = await session_repo.get_by_jti(claims["jti"])

    if existing is None or existing.token_hash != hash_refresh_token(raw_refresh_token):
        raise ApiError("Session expired or invalid — please log in again.", status_code=401)

    if not AuthSessionRepository.is_valid(existing):
        # Reuse of an already-rotated or revoked refresh token is a strong
        # signal of token theft — revoke every session for this user
        # rather than silently minting a new one.
        await session_repo.revoke_all_for_user(existing.user_id)
        await session.commit()
        raise ApiError("Session expired or invalid — please log in again.", status_code=401)

    user = await UserRepository(session).get_by_id(existing.user_id)
    if user is None or not user.is_active:
        raise ApiError("Session expired or invalid — please log in again.", status_code=401)

    access = create_access_token(settings, user.id)
    new_refresh = create_refresh_token(settings, user.id)
    new_session_row = AuthSession(
        user_id=user.id,
        jti=new_refresh.jti,
        token_hash=hash_refresh_token(new_refresh.token),
        issued_at=datetime.now(UTC),
        expires_at=new_refresh.expires_at,
        user_agent=user_agent,
    )
    session.add(new_session_row)
    await session.flush()

    await session_repo.revoke(existing, replaced_by_id=new_session_row.id)
    await session.commit()

    return user, TokenIssue(access=access, refresh=new_refresh)


async def logout_session(session: AsyncSession, settings: Settings, raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    try:
        claims = decode_refresh_token(settings, raw_refresh_token)
    except TokenError:
        return

    session_repo = AuthSessionRepository(session)
    existing = await session_repo.get_by_jti(claims["jti"])
    if existing is not None and existing.revoked_at is None:
        await session_repo.revoke(existing)
        await session.commit()


async def load_provider_profile(session: AsyncSession, user_id: str) -> Provider | None:
    return await ProviderRepository(session).get_by_user_id(user_id)
