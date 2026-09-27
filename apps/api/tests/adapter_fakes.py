"""Shared fake-HTTP-client helpers for adapter unit tests.

Adapter tests never touch the real network — a fake async client with
scripted responses is monkeypatched in place of get_http_client() so
normalization/error-handling/caching logic can be tested deterministically
and offline, per docs/PROJECT_STATE.md's Phase 4 testing approach.
"""

from __future__ import annotations

import json as json_lib
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx


def make_response(status_code: int, json: object = None, headers: dict[str, str] | None = None) -> httpx.Response:
    content = json_lib.dumps(json).encode() if json is not None else b""
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers or {},
        request=httpx.Request("GET", "https://example.invalid/"),
    )


@dataclass
class FakeAsyncClient:
    """Drop-in stand-in for httpx.AsyncClient's .get/.post used by adapters."""

    responder: Callable[..., httpx.Response]
    calls: list[dict] = field(default_factory=list)

    async def get(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: object | None = None,
    ) -> httpx.Response:
        self.calls.append({"method": "GET", "url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.responder(method="GET", url=url, params=params, headers=headers)

    async def post(
        self,
        url: str,
        data: dict | None = None,
        timeout: object | None = None,
    ) -> httpx.Response:
        self.calls.append({"method": "POST", "url": url, "data": data, "timeout": timeout})
        return self.responder(method="POST", url=url, data=data)


def sequence_responder(responses: list[httpx.Response]) -> Callable[..., httpx.Response]:
    iterator = iter(responses)

    def _respond(**_kwargs: object) -> httpx.Response:
        return next(iterator)

    return _respond


# ─── Fake google-genai SDK client (Phase 5) ────────────────────────────────
# GeminiAIAdapter uses the official SDK, not raw httpx, so its transport
# can't be faked via FakeAsyncClient/get_http_client. Instead these stand
# in for the exact async surface the adapter calls: client.aio.models.
# generate_content(...) and client.aio.auth_tokens.create(...). Tests
# monkeypatch src.adapters.ai.genai.Client to return a FakeGenAIClient.


@dataclass
class _AIO:
    models: object
    auth_tokens: object


@dataclass
class FakeGenAIModels:
    responder: Callable[..., object]
    calls: list[dict] = field(default_factory=list)

    async def generate_content(self, *, model: str, contents: object, config: object) -> object:
        self.calls.append({"model": model, "contents": contents, "config": config})
        result = self.responder(model=model, contents=contents, config=config)
        if isinstance(result, Exception):
            raise result
        return result


@dataclass
class FakeGenAIAuthTokens:
    responder: Callable[..., object]
    calls: list[dict] = field(default_factory=list)

    async def create(self, *, config: object) -> object:
        self.calls.append({"config": config})
        result = self.responder(config=config)
        if isinstance(result, Exception):
            raise result
        return result


class FakeGenAIClient:
    """Drop-in stand-in for google.genai.Client — only the .aio.models /
    .aio.auth_tokens surface GeminiAIAdapter actually uses."""

    def __init__(self, models_responder: Callable[..., object], auth_tokens_responder: Callable[..., object]) -> None:
        self.aio = _AIO(
            models=FakeGenAIModels(models_responder),
            auth_tokens=FakeGenAIAuthTokens(auth_tokens_responder),
        )
