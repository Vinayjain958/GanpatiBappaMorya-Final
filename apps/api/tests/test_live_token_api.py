from __future__ import annotations

from datetime import UTC

from tests.conftest import auth_header, register_provider, register_traveler


def test_live_token_requires_auth(discovery_client) -> None:
    response = discovery_client.post("/api/v1/auth/live-token")
    assert response.status_code == 401


def test_live_token_rejects_provider_role(discovery_client) -> None:
    provider = register_provider(discovery_client, "provider-voice@example.com", "Voice Test Co")
    response = discovery_client.post("/api/v1/auth/live-token", headers=auth_header(provider))
    assert response.status_code == 403


def test_live_token_mock_adapter_returns_unavailable_not_fake_success(discovery_client) -> None:
    """With MockAIAdapter (the default in tests), voice must never appear
    to succeed — a 503 here is the correct, honest behavior."""
    traveler = register_traveler(discovery_client, "traveler-voice@example.com")
    response = discovery_client.post("/api/v1/auth/live-token", headers=auth_header(traveler))
    assert response.status_code == 503


def test_live_token_success_shape_with_real_adapter(discovery_client, monkeypatch) -> None:
    from dataclasses import dataclass
    from datetime import datetime, timedelta

    from src.adapters.ai import LiveTokenIssueResult
    from src.core.ai import get_ai_adapter

    @dataclass
    class _FakeAdapter:
        async def issue_live_token(self) -> LiveTokenIssueResult:
            now = datetime.now(UTC)
            return LiveTokenIssueResult(
                token="auth_tokens/fake",
                expire_time=now + timedelta(minutes=30),
                new_session_expire_time=now + timedelta(minutes=1),
                model="gemini-3.8-live",
            )

        async def generate_text(self, prompt: str, *, response_schema: type) -> object:  # pragma: no cover
            raise NotImplementedError

    discovery_client.app.dependency_overrides[get_ai_adapter] = lambda: _FakeAdapter()
    try:
        traveler = register_traveler(discovery_client, "traveler-voice-success@example.com")
        response = discovery_client.post("/api/v1/auth/live-token", headers=auth_header(traveler))
        assert response.status_code == 200
        body = response.json()
        assert body["token"] == "auth_tokens/fake"
        assert body["model"] == "gemini-3.8-live"
        assert "expire_time" in body and "new_session_expire_time" in body
    finally:
        del discovery_client.app.dependency_overrides[get_ai_adapter]
