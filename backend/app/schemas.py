from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    details: str


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    cardIds: list[str]


class BoardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[Column]
    cards: dict[str, Card]

    @model_validator(mode="after")
    def _check_card_invariants(self) -> BoardData:
        for cid, card in self.cards.items():
            if cid != card.id:
                raise ValueError(
                    f"cards key '{cid}' does not match card.id '{card.id}'"
                )

        seen: set[str] = set()
        for col in self.columns:
            for ref in col.cardIds:
                if ref in seen:
                    raise ValueError(f"duplicate cardId in columns: '{ref}'")
                seen.add(ref)
                if ref not in self.cards:
                    raise ValueError(
                        f"orphan cardId in column '{col.id}': '{ref}' not in cards"
                    )

        for cid in self.cards:
            if cid not in seen:
                raise ValueError(
                    f"unreferenced cardId in cards: '{cid}' not in any column"
                )
        return self


DEFAULT_COLUMNS: list[Column] = [
    Column(id="col-backlog", title="Backlog", cardIds=[]),
    Column(id="col-discovery", title="Discovery", cardIds=[]),
    Column(id="col-progress", title="In Progress", cardIds=[]),
    Column(id="col-review", title="Review", cardIds=[]),
    Column(id="col-done", title="Done", cardIds=[]),
]


def empty_board() -> BoardData:
    return BoardData(columns=[c.model_copy() for c in DEFAULT_COLUMNS], cards={})
