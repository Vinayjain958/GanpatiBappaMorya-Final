"""Reusable FastAPI dependencies for authentication and authorization.

Centralizing these here means route handlers never hand-roll a token
check or a role check — see docs/AI_CONTEXT.md INV-3 and
docs/DECISIONS.md ADR-019 through ADR-021.

A stale `role` claim embedded in the JWT is never trusted as the sole
authorization source: `get_current_user` always re-loads the User row
from the database on every request, so a role change or deactivation
takes effect immediately rather than waiting for token expiry.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_session
from src.core.errors import ApiError
from src.core.security import TokenError, decode_access_token
from src.models.provider import Provider
from src.models.user import User
from src.repositories.provider_repository import ProviderRepository
from src.repositories.user_repository import UserRepository

# auto_error=False so a missing header raises our own consistent ApiError
# body instead of FastAPI's default 403 "Not authenticated" shape.
_bearer_scheme = HTTPBearer(auto_error=False, description="LocaLens access token (JWT)")


def _unauthorized() -> ApiError:
    return ApiError("Not authenticated", status_code=401)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()

    token = credentials.credentials.strip()
    if not token:
        raise _unauthorized()

    try:
        claims = decode_access_token(settings, token)
    except TokenError as exc:
        raise _unauthorized() from exc

    user_id = claims.get("sub")
    if not user_id:
        raise _unauthorized()

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ApiError("Insufficient role for this operation", status_code=403)
        return user

    return _dependency


require_traveler = require_role("traveler")
require_provider_role = require_role("provider")
require_admin = require_role("admin")


async def get_current_provider(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_provider_role)],
) -> Provider:
    """Loads the Provider profile owned by the current authenticated
    provider user. A `provider`-role user always has exactly one Provider
    row created transactionally at registration — a missing row here
    indicates data corruption, not a normal client-facing 404/403 case,
    so it is treated as an internal error rather than disclosed detail."""
    provider = await ProviderRepository(session).get_by_user_id(user.id)
    if provider is None:
        raise ApiError("Provider profile not found", status_code=404)
    return provider


CurrentProvider = Annotated[Provider, Depends(get_current_provider)]
