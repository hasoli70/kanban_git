from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """You are the assistant for a Kanban board application.

The user has a board with exactly five columns. Their IDs are fixed and you
must never add, remove, reorder, or change them:
  col-backlog, col-discovery, col-progress, col-review, col-done

You CAN do:
- Rename column titles (the visible text)
- Add new cards (pick a unique id like "card-<short-slug>")
- Edit card titles and details
- Move cards between columns
- Remove cards

You CANNOT do:
- Change any column id
- Add or remove columns
- Reorder columns

The current board state is provided as JSON in a separate system message.

You must always reply with a JSON object matching this exact schema:

{
  "reply": "<plain-text answer to the user, always present>",
  "board_update": <null OR the full new BoardData object>
}

Set "board_update" to null when the user is just asking a question or you
do not need to change the board. Set it to the COMPLETE new board state
(not a diff) when you want to apply changes. The shape of BoardData is:

{
  "columns": [
    {"id": "...", "title": "...", "cardIds": ["card-1", ...]},
    ...five entries with the fixed ids above...
  ],
  "cards": {
    "card-1": {"id": "card-1", "title": "...", "details": "..."},
    ...
  }
}

Rules for board_update:
- Every cardId referenced in columns[].cardIds MUST also appear as a key in cards.
- Every key in cards MUST be referenced by exactly one column.
- No duplicate cardIds across columns.
- "details" is a free-text string (empty string is fine if you have nothing to add).
"""


def board_context_message(board_json: str) -> dict[str, str]:
    """Return a system-role message embedding the current board JSON."""
    return {
        "role": "system",
        "content": f"Current board state:\n{board_json}",
    }


# Strict JSON schema for OpenRouter Structured Outputs (response_format).
# Keep it permissive enough for the model: detailed semantic validation runs
# server-side (see app.schemas.BoardData and app.ai.validate_chat_response).
AI_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "ai_response",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["reply", "board_update"],
        "properties": {
            "reply": {"type": "string"},
            "board_update": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["columns", "cards"],
                        "properties": {
                            "columns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["id", "title", "cardIds"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "title": {"type": "string"},
                                        "cardIds": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                            "cards": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["id", "title", "details"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "title": {"type": "string"},
                                        "details": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                ]
            },
        },
    },
}


RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": AI_RESPONSE_SCHEMA,
}
