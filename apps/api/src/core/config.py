"""Environment-based application configuration.

All settings are read from environment variables (see .env.example at the
repo root). The app must start in local development even when most
optional values are absent — see docs/AI_CONTEXT.md for the adapter
fallback contract.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = ""

    database_url: str = "sqlite+aiosqlite:///./localens_dev.db"

    # ─── AI — Google Gemini (Phase 5) ───────────────────────────────────────
    # gemini_enabled is a demo-room kill switch independent of key presence;
    # the real adapter is only used when both this is true AND a key is set.
    gemini_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model_text: str = "gemini-3.8-flash"
    gemini_model_live: str = "gemini-3.8-live"
    # Ephemeral Live token TTLs (Google's own defaults are 1 min / 30 min —
    # mirrored here as explicit, documented settings rather than SDK magic).
    gemini_live_token_ttl_seconds: int = 60
    gemini_live_session_ttl_seconds: int = 1800
    gemini_min_interval_seconds: float = 0.5
    # Bounded recent-turn window sent to the model on every text turn —
    # never unlimited conversation history (see docs/DECISIONS.md ADR-033).
    conversation_history_window: int = 12

    # ─── Semantic embeddings (Phase 6) ─────────────────────────────────────
    # Independent of gemini_enabled's text/Live gating in principle, but by
    # default follows the same real-vs-mock selection rule (see
    # src/core/embedding.py): GEMINI_ENABLED=true + key present -> real,
    # otherwise MockEmbeddingAdapter (deterministic, non-ML).
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_embedding_dimensions: int = 1536

    # ─── Semantic retrieval (Phase 6) ──────────────────────────────────────
    semantic_search_enabled: bool = True
    semantic_result_limit: int = 5
    semantic_candidate_pool_size: int = 50
    semantic_max_candidate_pool_size: int = 200

    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    osrm_base_url: str = "https://router.project-osrm.org"
    maptiler_api_key: str = ""

    # ─── Location services (Phase 4) ───────────────────────────────────────
    # Nominatim's usage policy requires a descriptive User-Agent identifying
    # the application (not a browser UA) and caps public-instance traffic at
    # 1 req/sec — see docs/DECISIONS.md ADR-022.
    nominatim_user_agent: str = "LocaLens/0.1 (hackathon-prototype; contact=dev@localens.example)"
    nominatim_min_interval_seconds: float = 1.0
    nominatim_cache_ttl_seconds: int = 3600

    overpass_base_url: str = "https://overpass-api.de/api/interpreter"
    overpass_min_interval_seconds: float = 2.0
    overpass_cache_ttl_seconds: int = 900
    overpass_max_radius_m: int = 2000

    osrm_profile: str = "driving"
    osrm_allowed_profiles: list[str] = Field(default_factory=lambda: ["driving", "walking", "cycling"])
    # The public OSRM demo server's own fair-use policy caps clients at
    # 1 req/sec — match that rather than the Nominatim-specific default.
    osrm_min_interval_seconds: float = 1.0
    osrm_cache_ttl_seconds: int = 900
    osrm_max_matrix_destinations: int = 25

    external_http_timeout_seconds: float = 8.0
    discovery_max_radius_km: float = 25.0
    discovery_candidate_cap: int = 1000

    # Real Nominatim/OSRM/Overpass adapters require no API key (all public
    # services) but can be force-disabled for offline dev/tests, falling
    # back to the Mock*Adapter implementations — see src/core/location.py.
    location_services_enabled: bool = True

    openweather_api_key: str = ""
    ticketmaster_api_key: str = ""

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # ─── Authentication (Phase 3) ──────────────────────────────────────────
    # Dev-only fallback secrets so the app still boots without a .env file.
    # validate_startup() below refuses to run in production with these.
    jwt_access_secret: str = "dev-insecure-access-secret-change-me"
    jwt_refresh_secret: str = "dev-insecure-refresh-secret-change-me"
    jwt_access_expires_minutes: int = 15
    jwt_refresh_expires_days: int = 7
    jwt_issuer: str = "localens"
    jwt_audience: str = "localens-app"

    refresh_cookie_name: str = ""  # "" -> computed from app_env in security.py
    cookie_secure: bool | None = None  # None -> True unless app_env == development
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str = ""  # "" -> no Domain attribute (host-only cookie)

    admin_seed_email: str = ""
    admin_seed_password: str = ""

    # ─── Personalized Ranking Engine (Phase 7) ──────────────────────────────────
    ranking_model_version: str = "weighted-v1"
    ranking_weight_semantic: float = 0.35
    ranking_weight_affinity: float = 0.25
    ranking_weight_preference: float = 0.20
    ranking_weight_budget: float = 0.05
    ranking_weight_duration: float = 0.05
    ranking_weight_distance: float = 0.05
    ranking_weight_novelty: float = 0.05

    affinity_learning_rate: float = 0.15
    affinity_recency_tau: int = 50
    recommendation_default_top_k: int = 10

    # ─── Itinerary Composer (Phase 8) ───────────────────────────────────────
    composer_default_max_experiences: int = 5
    composer_max_candidates: int = 20
    composer_max_optimization_iterations: int = 25
    # Post-composition validation re-checks each item's real feasibility
    # at its actual scheduled slot (opening hours/availability data the
    # earlier candidate-gate pass didn't have the specific time for yet).
    # A rejected item is excluded from the pool and composition retried,
    # bounded, rather than failing outright when a feasible replacement
    # candidate exists.
    composer_max_validation_retries: int = 5
    composer_min_buffer_minutes: int = 10
    composer_default_travel_mode: str = "driving"
    composer_narrative_model_version: str = "gemini-narrative-v1"
    composer_template_narrative_version: str = "template-fallback-v1"

    # ─── Real-time context: weather (Phase 9) ───────────────────────────────
    # Real adapter requires OPENWEATHER_API_KEY; falls back to
    # MockWeatherAdapter when absent or context_services_enabled=false —
    # mirrors src/core/location.py's fallback pattern (see src/core/context.py).
    context_services_enabled: bool = True
    weather_cache_ttl_seconds: int = 900
    weather_request_timeout_seconds: float = 8.0
    weather_min_interval_seconds: float = 1.0
    weather_monitor_interval_seconds: int = 600

    # ─── Real-time context: events (Phase 9) ────────────────────────────────
    events_cache_ttl_seconds: int = 1800
    events_request_timeout_seconds: float = 8.0
    events_min_interval_seconds: float = 1.0
    events_monitor_interval_seconds: int = 1800
    events_search_radius_m: int = 5000

    # ─── Public social context (optional Task 3 integration) ──────────────
    # Bluesky's public AppView search is read-only and needs no application
    # credential. Results are reduced to in-memory aggregate clusters only.
    social_signals_enabled: bool = True
    social_signal_request_timeout_seconds: float = 8.0
    social_signal_min_interval_seconds: float = 1.0
    social_signal_cache_ttl_seconds: int = 300
    social_signal_lookback_hours: int = 24
    social_signal_confidence_half_life_hours: float = 6.0

    # ─── Context impact thresholds (Phase 9) ────────────────────────────────
    weather_precipitation_probability_threshold: float = 60.0
    weather_precipitation_amount_mm_threshold: float = 2.0
    weather_wind_speed_threshold_ms: float = 12.0
    weather_temperature_extreme_low_c: float = 5.0
    weather_temperature_extreme_high_c: float = 40.0
    # Hysteresis band (percentage points) to avoid GOOD<->CAUTION
    # oscillation on small fluctuations around a threshold.
    weather_impact_hysteresis_pct: float = 10.0

    # ─── Dynamic replanning engine (Phase 9) ────────────────────────────────
    replanning_enabled: bool = True
    replan_narrative_model_version: str = "gemini-narrative-v1"
    replan_context_stale_after_seconds: int = 1800
    sse_heartbeat_interval_seconds: int = 15

    # ─── Phase 10 — Provider Intelligence ───────────────────────────────────
    provider_match_model_version: str = "provider-match-v1"
    provider_match_notification_threshold: float = 0.70
    provider_insight_min_segment_events: int = 5
    provider_match_weight_behavioral: float = 0.35
    provider_match_weight_category: float = 0.25
    provider_match_weight_preference: float = 0.15
    provider_match_weight_budget: float = 0.10
    provider_match_weight_duration: float = 0.10
    provider_match_weight_recency: float = 0.05
    provider_notification_cooldown_days: int = 7
    provider_insight_default_window: str = "30d"

    # ─── Phase 11 — Safety resources ────────────────────────────────────────
    # "auto" tries the live OSM/Overpass adapter first and falls back to the
    # deterministic seed adapter only on a genuine provider failure (network
    # error, timeout, malformed response) — never merely because live
    # returned zero results. "live" never falls back (surfaces a service
    # error instead); "fallback" always uses seed data.
    safety_resources_mode: Literal["auto", "live", "fallback"] = "auto"
    safety_resources_base_url: str = "https://overpass-api.de/api/interpreter"
    # Additional public Overpass mirrors tried in order, after the primary
    # base_url, when a request fails (timeout/5xx/429/504) — the public
    # instances load-shed independently, so a mirror often succeeds when
    # the primary doesn't. Never arbitrary/user-supplied (SSRF guard).
    safety_resources_mirror_urls: list[str] = Field(
        default_factory=lambda: [
            "https://overpass.kumi.systems/api/interpreter",
            "https://lz4.overpass-api.de/api/interpreter",
        ]
    )
    safety_resources_min_interval_seconds: float = 2.0
    safety_resources_cache_ttl_seconds: int = 900
    safety_resources_request_timeout_seconds: float = 10.0
    safety_resources_default_radius_km: float = 5.0
    safety_resources_min_radius_km: float = 0.5
    safety_resources_max_radius_km: float = 25.0

    # Second-tier live provider — tried only if the free Overpass/mirror
    # chain genuinely fails (auto mode). Requires a Mapbox access token;
    # when absent, this tier is skipped and auto mode falls straight
    # through to seed data on an Overpass failure, same as before this
    # tier existed. Never a hard startup requirement (docs/AI_CONTEXT.md
    # adapter fallback contract) — Safety must still boot without it.
    mapbox_api_key: str = ""
    mapbox_search_base_url: str = "https://api.mapbox.com/search/searchbox/v1/category"
    mapbox_request_timeout_seconds: float = 10.0
    mapbox_search_limit: int = 15

    # ─── Wikimedia Commons image resolution ─────────────────────────────────
    # No API key required — Wikimedia's public MediaWiki API is used
    # unauthenticated, but every request must send a meaningful
    # identifying User-Agent per Wikimedia's API etiquette
    # (https://meta.wikimedia.org/wiki/User-Agent_policy). This has a
    # documented, non-personal default so the app boots without a .env
    # file; set WIKIMEDIA_USER_AGENT to identify your own deployment.
    wikimedia_user_agent: str = "LocaLens/1.0 (https://github.com/localens; contact=dev@localens.example)"
    wikimedia_api_base_url: str = "https://commons.wikimedia.org/w/api.php"
    wikimedia_min_interval_seconds: float = 1.0
    wikimedia_cache_ttl_seconds: int = 86400
    wikimedia_request_timeout_seconds: float = 15.0
    # Geosearch radius escalation (meters) — start narrow, widen only when
    # no relevant result exists, never search an entire city per experience.
    wikimedia_geosearch_radii_m: list[int] = Field(default_factory=lambda: [1000, 3000, 5000])
    wikimedia_geosearch_limit: int = 20
    wikimedia_search_limit: int = 10
    # Below this deterministic match score, no image is selected at all —
    # "no suitable image" beats "wrong image" (see enrichment script).
    wikimedia_min_match_score: float = 20.0

    @model_validator(mode="after")
    def _validate_match_weights(self) -> Settings:
        total = sum([
            self.provider_match_weight_behavioral,
            self.provider_match_weight_category,
            self.provider_match_weight_preference,
            self.provider_match_weight_budget,
            self.provider_match_weight_duration,
            self.provider_match_weight_recency,
        ])
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Provider match weights must sum to 1.0 (tolerance ±0.001); "
                f"got {total:.6f}. Check provider_match_weight_* settings."
            )
        return self

    @model_validator(mode="after")
    def _validate_ranking_weights(self) -> Settings:
        total = sum([
            self.ranking_weight_semantic,
            self.ranking_weight_affinity,
            self.ranking_weight_preference,
            self.ranking_weight_budget,
            self.ranking_weight_duration,
            self.ranking_weight_distance,
            self.ranking_weight_novelty,
        ])
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Ranking weights must sum to 1.0 (tolerance ±0.001); "
                f"got {total:.6f}. Check ranking_weight_* settings."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_cookie_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env != "development"

    @property
    def effective_refresh_cookie_name(self) -> str:
        if self.refresh_cookie_name:
            return self.refresh_cookie_name
        # __Host- cookies require Secure + Path=/ + no Domain attribute.
        # Browsers silently reject them without Secure, so only use the
        # prefix when the cookie will actually be sent as Secure.
        return "__Host-localens_refresh" if self.effective_cookie_secure else "localens_refresh"


@lru_cache
def get_settings() -> Settings:
    return Settings()
