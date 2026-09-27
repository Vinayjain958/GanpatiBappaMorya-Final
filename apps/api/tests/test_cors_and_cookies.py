from __future__ import annotations

from src.core.config import get_settings


def test_cors_does_not_use_wildcard_with_credentials() -> None:
    settings = get_settings()
    assert "*" not in settings.cors_allow_origins
    assert settings.cors_allow_origins  # explicit origin list, never empty/wildcard


def test_credentialed_frontend_origin_allowed(client) -> None:
    response = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_refresh_cookie_flags(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookieflags@example.com",
            "password": "supersecret123",
            "role": "traveler",
            "display_name": "Cookie Flags",
        },
    )
    set_cookie = response.headers.get("set-cookie", "")
    lowered = set_cookie.lower()
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "path=/" in lowered
    # Local dev runs over HTTP — Secure is only forced in staging/production
    # (see Settings.effective_cookie_secure); asserting its *absence* here
    # would be environment-specific, so we only assert flags that always apply.
