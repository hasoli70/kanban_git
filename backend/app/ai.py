from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai_prompts import RESPONSE_FORMAT, SYSTEM_PROMPT, board_context_message
from app.auth import require_auth
from app.db import get_session
from app.models import Board, User
from app.schemas import BoardData

logger = logging.getLogger("app.ai")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_TIMEOUT_SECONDS = 30.0


class AIError(Exception):
    """Raised when the upstream AI call fails. Message is safe to surface to clients."""


async def call_openrouter(
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    body: dict[str, Any] = {"model": OPENROUTER_MODEL, "messages": messages}
    if response_format is not None:
        body["response_format"] = response_format

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
_DB = Depends(get_session)


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


# --- /api/ai/chat -----------------------------------------------------------

ALLOWED_HISTORY_ROLES = {"user", "assistant"}


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryMessage] = []


class ChatResponse(BaseModel):
    reply: str
    board_updated: bool
    validation_error: str | None = None


def _load_user_board(session: Session, username: str) -> Board:
    user = session.query(User).filter(User.username == username).one_or_none()
    if user is None or user.board is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="user has no board (seed missing)",
        )
    return user.board


def _build_messages(
    board_json: str, history: list[ChatHistoryMessage], message: str
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        board_context_message(board_json),
    ]
    for entry in history:
        if entry.role not in ALLOWED_HISTORY_ROLES:
            continue
        messages.append({"role": entry.role, "content": entry.content})
    messages.append({"role": "user", "content": message})
    return messages


def _parse_ai_payload(content: str) -> tuple[str, dict[str, Any] | None, str | None]:
    """Parse the model's JSON content into (reply, raw_board_update, error)."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return ("", None, "AI response was not valid JSON")
    if not isinstance(parsed, dict):
        return ("", None, "AI response was not a JSON object")
    reply = parsed.get("reply")
    if not isinstance(reply, str):
        return ("", None, "AI response missing 'reply' string")
    board_update = parsed.get("board_update", None)
    if board_update is not None and not isinstance(board_update, dict):
        return (reply, None, "AI response 'board_update' was not an object or null")
    return (reply, board_update, None)


def _validate_board_update(
    raw_board: dict[str, Any], current: BoardData
) -> tuple[BoardData | None, str | None]:
    try:
        proposed = BoardData.model_validate(raw_board)
    except ValidationError as exc:
        return (None, f"proposed board failed validation: {exc.errors()[0]['msg']}")

    current_ids = [c.id for c in current.columns]
    new_ids = [c.id for c in proposed.columns]
    if current_ids != new_ids:
        return (
            None,
            "column ids cannot be added, removed, or reordered (rename only)",
        )
    return (proposed, None)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: str = _AUTH,
    session: Session = _DB,
) -> ChatResponse:
    board = _load_user_board(session, user)
    current = BoardData.model_validate_json(board.data)
    messages = _build_messages(board.data, payload.history, payload.message)

    try:
        result = await call_openrouter(messages, response_format=RESPONSE_FORMAT)
    except AIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    reply, raw_board, parse_error = _parse_ai_payload(result["content"])
    if parse_error is not None:
        return ChatResponse(
            reply=reply or "", board_updated=False, validation_error=parse_error
        )

    if raw_board is None:
        return ChatResponse(reply=reply, board_updated=False)

    proposed, validation_error = _validate_board_update(raw_board, current)
    if validation_error is not None:
        return ChatResponse(
            reply=reply, board_updated=False, validation_error=validation_error
        )

    assert proposed is not None
    board.data = proposed.model_dump_json()
    session.commit()
    session.refresh(board)
    return ChatResponse(reply=reply, board_updated=True)
