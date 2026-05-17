from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_auth

logger = logging.getLogger("app.ai")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_TIMEOUT_SECONDS = 30.0


class AIError(Exception):
    """Raised when the upstream AI call fails. Message is safe to surface to clients."""


async def call_openrouter(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Call OpenRouter chat completions and return content + token usage.

    Returns a dict with keys: content (str), prompt_tokens (int), completion_tokens (int).
    Raises AIError on any failure. The API key is never included in the exception message.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise AIError("AI provider is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"model": OPENROUTER_MODEL, "messages": messages}

    try:
        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT_SECONDS) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        logger.warning("openrouter timeout after %ss", OPENROUTER_TIMEOUT_SECONDS)
        raise AIError("AI provider timed out") from exc
    except httpx.HTTPError as exc:
        logger.warning("openrouter transport error: %s", type(exc).__name__)
        raise AIError("AI provider unreachable") from exc

    if response.status_code >= 400:
        logger.warning(
            "openrouter http %s (model=%s)", response.status_code, OPENROUTER_MODEL
        )
        raise AIError("AI provider returned an error")

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        logger.warning("openrouter malformed response: %s", type(exc).__name__)
        raise AIError("AI provider returned an unexpected response") from exc

    logger.info(
        "openrouter call ok model=%s prompt_tokens=%d completion_tokens=%d",
        OPENROUTER_MODEL,
        prompt_tokens,
        completion_tokens,
    )

    return {
        "content": content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


router = APIRouter(prefix="/api/ai", tags=["ai"])

_AUTH = Depends(require_auth)


class PingResponse(BaseModel):
    reply: str


@router.post("/ping", response_model=PingResponse)
async def ping(_user: str = _AUTH) -> PingResponse:
    messages = [
        {"role": "user", "content": "What is 2+2? Reply with just the number."}
    ]
    try:
        result = await call_openrouter(messages)
    except AIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return PingResponse(reply=result["content"])
