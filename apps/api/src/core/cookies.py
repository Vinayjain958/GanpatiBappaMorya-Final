"""HttpOnly refresh-token cookie helpers.

The refresh token is never returned in a JSON body — only ever set as an
HttpOnly cookie the browser attaches automatically to /api/v1/auth/*
requests. See docs/DECISIONS.md ADR-019.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Response

from src.core.config import Settings

# "/" is required by the `__Host-` cookie prefix (Secure + Path=/ + no
# Domain attribute) — see effective_refresh_cookie_name in config.py.
# HttpOnly + SameSite + Secure already scope the cookie tightly; we don't
# additionally restrict Path since that would break the __Host- prefix.
REFRESH_COOKIE_PATH = "/"


def set_refresh_cookie(response: Response, settings: Settings, token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=settings.effective_refresh_cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        path=REFRESH_COOKIE_PATH,
        domain=settings.cookie_domain or None,
        secure=settings.effective_cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.effective_refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
        domain=settings.cookie_domain or None,
        secure=settings.effective_cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
