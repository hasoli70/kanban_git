from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import app


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 204


def test_ai_ping_unauthenticated() -> None:
    client = TestClient(app)
    response = client.post("/api/ai/ping")
    assert response.status_code == 401


def test_ai_ping_returns_upstream_content(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(_messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {"content": "4", "prompt_tokens": 12, "completion_tokens": 3}

    monkeypatch.setattr(ai, "call_openrouter", fake_call)
    client = TestClient(app)
    _login(client)

    response = client.post("/api/ai/ping")
    assert response.status_code == 200
    assert response.json() == {"reply": "4"}


def test_ai_ping_maps_provider_error_to_502(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call(_messages: list[dict[str, Any]]) -> dict[str, Any]:
        raise ai.AIError("AI provider timed out")

    monkeypatch.setattr(ai, "call_openrouter", fake_call)
    client = TestClient(app)
    _login(client)

    response = client.post("/api/ai/ping")
    assert response.status_code == 502
    assert response.json()["detail"] == "AI provider timed out"


def test_call_openrouter_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    import asyncio

    with pytest.raises(ai.AIError):
        asyncio.run(ai.call_openrouter([{"role": "user", "content": "hi"}]))


def test_call_openrouter_logs_token_counts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == ai.OPENROUTER_URL
        assert request.headers["authorization"] == "Bearer test-key-not-real"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 42, "completion_tokens": 7},
            },
        )

    transport = httpx.MockTransport(handler)

    real_async_client = httpx.AsyncClient

    def patched_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(ai.httpx, "AsyncClient", patched_async_client)

    import asyncio

    with caplog.at_level(logging.INFO, logger="app.ai"):
        result = asyncio.run(ai.call_openrouter([{"role": "user", "content": "hi"}]))

    assert result == {"content": "ok", "prompt_tokens": 42, "completion_tokens": 7}
    log_message = "\n".join(record.getMessage() for record in caplog.records)
    assert "prompt_tokens=42" in log_message
    assert "completion_tokens=7" in log_message
    assert "test-key-not-real" not in log_message


def test_call_openrouter_timeout_raises_aierror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(ai.httpx, "AsyncClient", patched_async_client)

    import asyncio

    with pytest.raises(ai.AIError) as excinfo:
        asyncio.run(ai.call_openrouter([{"role": "user", "content": "hi"}]))
    assert "timed out" in str(excinfo.value)
    assert "test-key-not-real" not in str(excinfo.value)


def test_call_openrouter_upstream_4xx_raises_aierror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limit"})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(ai.httpx, "AsyncClient", patched_async_client)

    import asyncio

    with pytest.raises(ai.AIError):
        asyncio.run(ai.call_openrouter([{"role": "user", "content": "hi"}]))


def test_call_openrouter_null_content_raises_aierror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": None}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 0},
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(ai.httpx, "AsyncClient", patched_async_client)

    import asyncio

    with pytest.raises(ai.AIError, match="empty response"):
        asyncio.run(ai.call_openrouter([{"role": "user", "content": "hi"}]))


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set; skipping live integration test",
)
def test_ai_ping_returns_4_live() -> None:
    client = TestClient(app)
    _login(client)
    response = client.post("/api/ai/ping")
    assert response.status_code == 200
    assert "4" in response.json()["reply"]
