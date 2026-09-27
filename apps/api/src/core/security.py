"""Password hashing and JWT issuance/verification.

Passwords: Argon2 via pwdlib. Never log, return, or persist plaintext.
Tokens: two HS256-signed JWTs with distinct secrets (docs/DECISIONS.md
ADR-019) — a short-lived access token (kept in browser memory only) and a
longer-lived refresh token (kept server-side as a hash + HttpOnly cookie).
A stale `role` claim is never trusted for authorization by itself — see
src/core/deps.py, which re-loads the user from the database on every request.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from pwdlib import PasswordHash

from src.core.config import Settings

_password_hasher = PasswordHash.recommended()


def hash_password(raw_password: str) -> str:
    return _password_hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(raw_password, password_hash)
    except Exception:
        return False


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Raised for any invalid/expired/malformed token. Never leaks details to clients."""


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    expires_at: datetime


def _encode(
    *, settings: Settings, secret: str, subject: str, token_type: TokenType, expires_delta: timedelta
) -> IssuedToken:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "jti": jti,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def create_access_token(settings: Settings, user_id: str) -> IssuedToken:
    return _encode(
        settings=settings,
        secret=settings.jwt_access_secret,
        subject=user_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.jwt_access_expires_minutes),
    )


def create_refresh_token(settings: Settings, user_id: str) -> IssuedToken:
    return _encode(
        settings=settings,
        secret=settings.jwt_refresh_secret,
        subject=user_id,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.jwt_refresh_expires_days),
    )


def _decode(*, settings: Settings, secret: str, token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "jti", "type", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if claims.get("type") != expected_type.value:
        raise TokenError("Unexpected token type")
    return claims


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    return _decode(settings=settings, secret=settings.jwt_access_secret, token=token, expected_type=TokenType.ACCESS)


def decode_refresh_token(settings: Settings, token: str) -> dict[str, Any]:
    return _decode(
        settings=settings, secret=settings.jwt_refresh_secret, token=token, expected_type=TokenType.REFRESH
    )


def hash_refresh_token(token: str) -> str:
    """One-way hash used for revocation-safe storage — the raw refresh
    token is never persisted (docs/DECISIONS.md ADR-020)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_dev_password(length: int = 20) -> str:
    """Used only by scripts/create_admin.py when no password is supplied."""
    return secrets.token_urlsafe(length)
