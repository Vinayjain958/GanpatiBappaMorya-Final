"""Tests for the AI adapter (Phase 5) — MockAIAdapter and GeminiAIAdapter.

Never calls real Gemini: the real-adapter tests monkeypatch
src.adapters.ai.genai.Client with FakeGenAIClient.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from google.genai import errors as genai_errors

from src.adapters.ai import GeminiAIAdapter, MockAIAdapter
from src.adapters.errors import AdapterNoResultError, AdapterRateLimitedError, AdapterUnavailableError
from src.core.config import Settings
from src.schemas.conversation import TravelerContext
from src.services.ai_tools import CHECK_FEASIBILITY_DECLARATION, SEARCH_EXPERIENCES_DECLARATION
from tests.adapter_fakes import FakeGenAIClient


def _settings(**overrides: object) -> Settings:
    return Settings(
        gemini_enabled=True,
        gemini_api_key="test-key",
        gemini_model_text="gemini-3.8-flash",
        gemini_model_live="gemini-3.8-live",
        gemini_min_interval_seconds=0.0,
        **overrides,  # type: ignore[arg-type]
    )


def test_mock_adapter_generate_text_never_raises() -> None:
    adapter = MockAIAdapter()
    context = asyncio.run(
        adapter.generate_text("I want cheap local food near Fort", response_schema=TravelerContext)
    )
    assert isinstance(context, TravelerContext)
    assert context.raw_query == "I want cheap local food near Fort"
    assert "cheap" in context.interests or "local" in context.interests or "food" in context.interests


def test_mock_adapter_issue_live_token_raises_unavailable() -> None:
    adapter = MockAIAdapter()
    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.issue_live_token())


def _install_fake_client(monkeypatch, fake: FakeGenAIClient) -> None:
    monkeypatch.setattr("src.adapters.ai.genai.Client", lambda **_kwargs: fake)


def test_real_adapter_generate_text_success(monkeypatch) -> None:
    parsed = TravelerContext(raw_query="cheap food near Fort", interests=["food"])

    @dataclass
    class FakeResponse:
        text: str

    def models_responder(**_kwargs: object) -> FakeResponse:
        return FakeResponse(text=parsed.model_dump_json())

    fake = FakeGenAIClient(models_responder=models_responder, auth_tokens_responder=lambda **_: None)
    _install_fake_client(monkeypatch, fake)

    adapter = GeminiAIAdapter(_settings(), [SEARCH_EXPERIENCES_DECLARATION, CHECK_FEASIBILITY_DECLARATION])
    result = asyncio.run(adapter.generate_text("cheap food near Fort", response_schema=TravelerContext))
    assert result == parsed


def test_real_adapter_generate_text_empty_response_raises_no_result(monkeypatch) -> None:
    @dataclass
    class FakeResponse:
        text: str | None

    def models_responder(**_kwargs: object) -> FakeResponse:
        return FakeResponse(text=None)

    fake = FakeGenAIClient(models_responder=models_responder, auth_tokens_responder=lambda **_: None)
    _install_fake_client(monkeypatch, fake)

    adapter = GeminiAIAdapter(_settings(), [SEARCH_EXPERIENCES_DECLARATION, CHECK_FEASIBILITY_DECLARATION])
    with pytest.raises(AdapterNoResultError):
        asyncio.run(adapter.generate_text("hello", response_schema=TravelerContext))


def test_real_adapter_generate_text_rate_limited(monkeypatch) -> None:
    def models_responder(**_kwargs: object) -> Exception:
        return genai_errors.ClientError(code=429, response_json={"error": "rate limited"})

    fake = FakeGenAIClient(models_responder=models_responder, auth_tokens_responder=lambda **_: None)
    _install_fake_client(monkeypatch, fake)

    adapter = GeminiAIAdapter(_settings(), [SEARCH_EXPERIENCES_DECLARATION, CHECK_FEASIBILITY_DECLARATION])
    with pytest.raises(AdapterRateLimitedError):
        asyncio.run(adapter.generate_text("hello", response_schema=TravelerContext))


def test_real_adapter_generate_text_server_error_unavailable(monkeypatch) -> None:
    def models_responder(**_kwargs: object) -> Exception:
        return genai_errors.ServerError(code=503, response_json={"error": "down"})

    fake = FakeGenAIClient(models_responder=models_responder, auth_tokens_responder=lambda **_: None)
    _install_fake_client(monkeypatch, fake)

    adapter = GeminiAIAdapter(_settings(), [SEARCH_EXPERIENCES_DECLARATION, CHECK_FEASIBILITY_DECLARATION])
    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.generate_text("hello", response_schema=TravelerContext))


def test_real_adapter_issue_live_token_success(monkeypatch) -> None:
    now = datetime.now(UTC)

    @dataclass
    class FakeToken:
        name: str
        expire_time: datetime
        new_session_expire_time: datetime

    def auth_tokens_responder(**_kwargs: object) -> FakeToken:
        return FakeToken(
            name="auth_tokens/abc123",
            expire_time=now + timedelta(minutes=30),
            new_session_expire_time=now + timedelta(minutes=1),
        )

    fake = FakeGenAIClient(models_responder=lambda **_: None, auth_tokens_responder=auth_tokens_responder)
    _install_fake_client(monkeypatch, fake)

    adapter = GeminiAIAdapter(_settings(), [SEARCH_EXPERIENCES_DECLARATION, CHECK_FEASIBILITY_DECLARATION])
    result = asyncio.run(adapter.issue_live_token())
    assert result.token == "auth_tokens/abc123"
    assert result.model == "gemini-3.8-live"


def test_real_adapter_issue_live_token_failure_translates(monkeypatch) -> None:
    def auth_tokens_responder(**_kwargs: object) -> Exception:
        return genai_errors.ClientError(code=500, response_json={"error": "boom"})

    fake = FakeGenAIClient(models_responder=lambda **_: None, auth_tokens_responder=auth_tokens_responder)
    _install_fake_client(monkeypatch, fake)

    adapter = GeminiAIAdapter(_settings(), [SEARCH_EXPERIENCES_DECLARATION, CHECK_FEASIBILITY_DECLARATION])
    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.issue_live_token())
