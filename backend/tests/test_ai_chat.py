from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import ai


def _mock_ai_returning(content: str) -> Any:
    async def fake_call(
        _messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert response_format is not None, "chat must request structured output"
        return {"content": content, "prompt_tokens": 1, "completion_tokens": 1}

    return fake_call


def test_chat_unauthenticated(client: TestClient) -> None:
    response = client.post("/api/ai/chat", json={"message": "hi", "history": []})
    assert response.status_code == 401


def test_chat_simple_question_no_board_update(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.dumps(
        {"reply": "You have zero cards in Backlog.", "board_update": None}
    )
    monkeypatch.setattr(ai, "call_openrouter", _mock_ai_returning(payload))

    response = auth_client.post(
        "/api/ai/chat",
        json={"message": "How many cards in Backlog?", "history": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "You have zero cards in Backlog."
    assert body["board_updated"] is False
    assert body["validation_error"] is None

    board = auth_client.get("/api/board").json()
    assert board["cards"] == {}


def test_chat_modify_board_persists(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = auth_client.get("/api/board").json()
    new_board = json.loads(json.dumps(current))
    new_board["cards"] = {
        "card-ai1": {"id": "card-ai1", "title": "Built by AI", "details": "from chat"}
    }
    new_board["columns"][0]["cardIds"] = ["card-ai1"]

    payload = json.dumps({"reply": "Added the card.", "board_update": new_board})
    monkeypatch.setattr(ai, "call_openrouter", _mock_ai_returning(payload))

    response = auth_client.post(
        "/api/ai/chat",
        json={"message": "Add a card 'Built by AI' to Backlog", "history": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["board_updated"] is True
    assert body["validation_error"] is None

    refetched = auth_client.get("/api/board").json()
    assert refetched["cards"]["card-ai1"]["title"] == "Built by AI"
    assert refetched["columns"][0]["cardIds"] == ["card-ai1"]


def test_chat_rejects_column_id_change(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = auth_client.get("/api/board").json()
    bad_board = json.loads(json.dumps(current))
    bad_board["columns"][0]["id"] = "col-renamed"

    payload = json.dumps({"reply": "Renamed it.", "board_update": bad_board})
    monkeypatch.setattr(ai, "call_openrouter", _mock_ai_returning(payload))

    response = auth_client.post(
        "/api/ai/chat",
        json={"message": "Rename the first column id", "history": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["board_updated"] is False
    assert body["validation_error"] is not None
    assert "column ids" in body["validation_error"]

    refetched = auth_client.get("/api/board").json()
    assert [c["id"] for c in refetched["columns"]] == [c["id"] for c in current["columns"]]


def test_chat_rejects_orphan_cardid(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = auth_client.get("/api/board").json()
    bad_board = json.loads(json.dumps(current))
    bad_board["columns"][0]["cardIds"] = ["card-ghost"]
    # cards is still empty -> orphan reference

    payload = json.dumps({"reply": "Done.", "board_update": bad_board})
    monkeypatch.setattr(ai, "call_openrouter", _mock_ai_returning(payload))

    response = auth_client.post(
        "/api/ai/chat",
        json={"message": "Add a ghost card", "history": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["board_updated"] is False
    assert body["validation_error"] is not None

    refetched = auth_client.get("/api/board").json()
    assert refetched["columns"][0]["cardIds"] == []
    assert refetched["cards"] == {}


def test_chat_handles_invalid_json_from_ai(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai, "call_openrouter", _mock_ai_returning("not json at all"))

    response = auth_client.post(
        "/api/ai/chat", json={"message": "hello", "history": []}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["board_updated"] is False
    assert body["validation_error"] is not None


def test_chat_provider_error_maps_to_502(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_call(
        _messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise ai.AIError("AI provider timed out")

    monkeypatch.setattr(ai, "call_openrouter", fake_call)

    response = auth_client.post(
        "/api/ai/chat", json={"message": "hi", "history": []}
    )
    assert response.status_code == 502


def test_chat_includes_system_and_board_messages(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    async def fake_call(
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        captured["messages"] = messages
        captured["response_format"] = response_format
        return {
            "content": json.dumps({"reply": "ok", "board_update": None}),
            "prompt_tokens": 1,
            "completion_tokens": 1,
        }

    monkeypatch.setattr(ai, "call_openrouter", fake_call)

    history = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    response = auth_client.post(
        "/api/ai/chat", json={"message": "follow-up", "history": history}
    )
    assert response.status_code == 200

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system" and "Kanban" in msgs[0]["content"]
    assert msgs[1]["role"] == "system" and "Current board state" in msgs[1]["content"]
    assert msgs[2] == {"role": "user", "content": "earlier question"}
    assert msgs[3] == {"role": "assistant", "content": "earlier answer"}
    assert msgs[-1] == {"role": "user", "content": "follow-up"}

    rf = captured["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "ai_response"
