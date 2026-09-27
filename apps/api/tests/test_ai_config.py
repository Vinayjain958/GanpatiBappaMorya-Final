from __future__ import annotations

from src.adapters.ai import GeminiAIAdapter, MockAIAdapter
from src.core.ai import get_ai_adapter
from src.core.config import Settings


def test_model_defaults_are_current() -> None:
    # Settings() reads the real project .env (model_config.env_file), so a
    # developer's locally-chosen model overrides the class default there —
    # assert against the Settings class's own hardcoded fallback instead,
    # which is what "current" actually means here.
    assert Settings.model_fields["gemini_model_text"].default == "gemini-3.8-flash"
    assert Settings.model_fields["gemini_model_live"].default == "gemini-3.8-live"


def test_get_ai_adapter_returns_mock_when_disabled(monkeypatch) -> None:
    def _settings() -> Settings:
        return Settings(gemini_enabled=False, gemini_api_key="some-key")

    monkeypatch.setattr("src.core.ai.get_settings", _settings)
    get_ai_adapter.cache_clear()
    try:
        adapter = get_ai_adapter()
        assert isinstance(adapter, MockAIAdapter)
    finally:
        get_ai_adapter.cache_clear()


def test_get_ai_adapter_returns_mock_when_key_missing(monkeypatch) -> None:
    def _settings() -> Settings:
        return Settings(gemini_enabled=True, gemini_api_key="")

    monkeypatch.setattr("src.core.ai.get_settings", _settings)
    get_ai_adapter.cache_clear()
    try:
        adapter = get_ai_adapter()
        assert isinstance(adapter, MockAIAdapter)
    finally:
        get_ai_adapter.cache_clear()


def test_get_ai_adapter_returns_real_when_enabled_and_keyed(monkeypatch) -> None:
    def _settings() -> Settings:
        return Settings(gemini_enabled=True, gemini_api_key="a-real-looking-key")

    monkeypatch.setattr("src.core.ai.get_settings", _settings)
    get_ai_adapter.cache_clear()
    try:
        adapter = get_ai_adapter()
        assert isinstance(adapter, GeminiAIAdapter)
    finally:
        get_ai_adapter.cache_clear()
