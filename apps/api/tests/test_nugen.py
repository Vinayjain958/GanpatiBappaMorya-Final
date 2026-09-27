"""Mocked unit coverage for the server-side Nugen adapter and service."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from src.adapters.errors import AdapterRateLimitedError, AdapterTimeoutError, AdapterUnavailableError
from src.api.v1.domain_intelligence import get_domain_intelligence_health
from src.core.config import Settings, get_settings
from src.core.digital_twin import get_domain_intelligence_provider
from src.integrations.nugen.client import NugenClient
from src.integrations.nugen.schemas import NugenMessage
from src.schemas.domain_intelligence import DomainIntelligenceInput
from src.services.nugen_domain_intelligence import NugenDomainIntelligenceService

TEST_KEY = "nugen-unit-test-secret-never-log"


def _settings() -> Settings:
    return Settings(
        nugen_api_key=TEST_KEY,
        nugen_model_endpoint="https://api.nugen.test/chat/completions",
        nugen_model_id="model_test_123",
    )


def _run(coro):
    return asyncio.run(coro)


def test_successful_request_parses_content_and_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.nugen.test/chat/completions"
        assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
        assert request.headers["content-type"] == "application/json"
        body = json.loads(request.content)
        assert body == {
            "model": "model_test_123",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 800,
            "temperature": 0.2,
            "stream": False,
        }
        return httpx.Response(
            200,
            json={
                "model": "model_test_123",
                "choices": [{"message": {"content": "A structured answer."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
                "confidence_score": 0.73,
            },
        )

    client = NugenClient(_settings(), transport=httpx.MockTransport(handler))
    result = _run(client.complete([NugenMessage(role="user", content="hello")]))
    assert result.content == "A structured answer."
    assert result.model == "model_test_123"
    assert result.usage == {"prompt_tokens": 12, "completion_tokens": 5}
    assert result.confidence_score == 0.73
    assert result.finish_reason == "stop"


@pytest.mark.parametrize("status_code", [401, 403, 404, 422, 500, 503])
def test_http_failures_are_safe(status_code: int) -> None:
    client = NugenClient(
        _settings(), transport=httpx.MockTransport(lambda _: httpx.Response(status_code, text=TEST_KEY))
    )
    with pytest.raises(AdapterUnavailableError) as raised:
        _run(client.complete([NugenMessage(role="user", content="hello")]))
    assert TEST_KEY not in str(raised.value)


def test_rate_limit_and_retry_after_are_exposed_without_response_body() -> None:
    client = NugenClient(
        _settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"Retry-After": "3"}, text=TEST_KEY)
        ),
    )
    with pytest.raises(AdapterRateLimitedError) as raised:
        _run(client.complete([NugenMessage(role="user", content="hello")]))
    assert raised.value.retry_after_seconds == 3
    assert TEST_KEY not in str(raised.value)


def test_timeout_is_translated_to_safe_adapter_error() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout with credential " + TEST_KEY)

    client = NugenClient(_settings(), transport=httpx.MockTransport(timeout))
    with pytest.raises(AdapterTimeoutError) as raised:
        _run(client.complete([NugenMessage(role="user", content="hello")]))
    assert TEST_KEY not in str(raised.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
    ],
)
def test_malformed_chat_response_is_rejected(response: httpx.Response) -> None:
    client = NugenClient(_settings(), transport=httpx.MockTransport(lambda _: response))
    with pytest.raises(AdapterUnavailableError, match="malformed response"):
        _run(client.complete([NugenMessage(role="user", content="hello")]))


def test_transport_unavailable_is_safe() -> None:
    def unavailable(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection details with " + TEST_KEY)

    client = NugenClient(_settings(), transport=httpx.MockTransport(unavailable))
    with pytest.raises(AdapterUnavailableError) as raised:
        _run(client.complete([NugenMessage(role="user", content="hello")]))
    assert TEST_KEY not in str(raised.value)


def test_domain_service_parses_structured_result_and_does_not_invent_confidence() -> None:
    response = {
        "model": "model_test_123",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "analysis": "Assess the observed rain against verified suitability.",
                            "impacts": ["Outdoor comfort may be reduced."],
                            "suitability_assessment": "Outdoor suitability may be reduced during heavy rain.",
                            "disruption_assessment": "No route closure is verified by this scenario.",
                            "recommendation": "Review indoor alternatives and authoritative route/weather data.",
                            "uncertainty": "Stop-specific forecast details are limited.",
                            "reason_codes": ["WEATHER_OBSERVED"],
                        }
                    )
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"total_tokens": 44},
    }
    client = NugenClient(_settings(), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    service = NugenDomainIntelligenceService(client)
    result = _run(service.analyze(DomainIntelligenceInput(scenario_name="Heavy rain")))
    assert result.provider == "nugen"
    assert result.summary.startswith("Assess the observed rain")
    assert result.impacts == ["Outdoor comfort may be reduced."]
    assert result.suitability_assessment.startswith("Outdoor suitability")
    assert result.disruption_assessment.startswith("No route closure")
    assert result.recommendation.startswith("Review indoor alternatives")
    assert result.model_id == "model_test_123"
    assert result.usage == {"total_tokens": 44}
    assert result.confidence_score is None


def test_api_key_is_never_logged(caplog) -> None:
    client = NugenClient(
        _settings(), transport=httpx.MockTransport(lambda _: httpx.Response(401, text=TEST_KEY))
    )
    with pytest.raises(AdapterUnavailableError):
        _run(client.complete([NugenMessage(role="user", content="hello")]))
    assert TEST_KEY not in caplog.text


def test_nugen_settings_require_model_id_when_key_enables_integration() -> None:
    with pytest.raises(ValidationError):
        Settings(nugen_api_key=TEST_KEY, nugen_model_id="   ")


def test_provider_selection_keeps_mock_when_nugen_is_not_configured() -> None:
    assert get_domain_intelligence_provider(Settings(nugen_api_key="")).__class__.__name__ == (
        "MockDomainIntelligenceProvider"
    )
    assert get_domain_intelligence_provider(_settings()).__class__.__name__ == "NugenDomainIntelligenceService"


def test_safe_health_diagnostic_exposes_model_id_but_no_secret() -> None:
    settings = _settings()
    response = _run(get_domain_intelligence_health(settings=settings))
    serialized = response.model_dump(mode="json")
    assert serialized == {"configured": True, "model_id": "model_test_123"}
    assert TEST_KEY not in json.dumps(serialized)


def test_health_route_never_exposes_nugen_secret(discovery_client) -> None:
    discovery_client.app.dependency_overrides[get_settings] = _settings
    response = discovery_client.get("/api/v1/domain-intelligence/health")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "model_id": "model_test_123"}
    assert TEST_KEY not in response.text
