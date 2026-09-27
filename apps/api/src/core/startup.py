"""Environment startup validation.

Warns on missing optional service credentials (adapters fall back to
mocks) and fails fast on missing required production configuration.
"""

from __future__ import annotations

import logging

from src.core.config import Settings

logger = logging.getLogger("localens.startup")

_OPTIONAL_KEYS = {
    "gemini_api_key": "Gemini AI features",
    "maptiler_api_key": "Premium map tiles (OSM tiles used as fallback)",
    "openweather_api_key": "Weather adapter",
    "ticketmaster_api_key": "Event adapter",
    "supabase_service_role_key": "Supabase-backed production database",
}


_DEV_INSECURE_JWT_SECRETS = {
    "dev-insecure-access-secret-change-me",
    "dev-insecure-refresh-secret-change-me",
}


def validate_startup(settings: Settings) -> None:
    if settings.is_production and not settings.app_secret_key:
        raise RuntimeError("APP_SECRET_KEY is required in production.")

    if settings.is_production and (
        settings.jwt_access_secret in _DEV_INSECURE_JWT_SECRETS
        or settings.jwt_refresh_secret in _DEV_INSECURE_JWT_SECRETS
        or settings.jwt_access_secret == settings.jwt_refresh_secret
    ):
        raise RuntimeError(
            "JWT_ACCESS_SECRET and JWT_REFRESH_SECRET must be set to distinct, "
            "non-default values in production."
        )

    if settings.admin_seed_password and len(settings.admin_seed_password) < 12:
        logger.warning("ADMIN_SEED_PASSWORD is set but shorter than 12 characters.")

    for field_name, purpose in _OPTIONAL_KEYS.items():
        if not getattr(settings, field_name):
            logger.warning(
                "Optional credential '%s' is not set — %s will use a mock/fallback implementation.",
                field_name.upper(),
                purpose,
            )
