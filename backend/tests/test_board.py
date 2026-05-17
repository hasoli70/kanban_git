from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session, make_engine, seed_default_user
from app.main import app
from app.models import Base


def test_init_db_creates_user_and_empty_board(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 204

    board = client.get("/api/board")
    assert board.status_code == 200
    payload = board.json()
    assert [c["id"] for c in payload["columns"]] == [
        "col-backlog",
        "col-discovery",
        "col-progress",
        "col-review",
        "col-done",
    ]
    assert all(col["cardIds"] == [] for col in payload["columns"])
    assert payload["cards"] == {}


def test_get_board_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/board")
    assert response.status_code == 401


def test_put_board_persists(auth_client: TestClient) -> None:
    current = auth_client.get("/api/board").json()
    current["columns"][0]["title"] = "Idee"
    current["columns"][0]["cardIds"] = ["card-new"]
    current["cards"] = {
        "card-new": {"id": "card-new", "title": "Test", "details": "Note"}
    }

    response = auth_client.put("/api/board", json=current)
    assert response.status_code == 200

    refetched = auth_client.get("/api/board").json()
    assert refetched["columns"][0]["title"] == "Idee"
    assert refetched["cards"]["card-new"]["title"] == "Test"


def test_put_board_orphan_cardid_rejected(auth_client: TestClient) -> None:
    current = auth_client.get("/api/board").json()
    current["columns"][0]["cardIds"] = ["card-ghost"]
    # no entry in cards -> orphan reference

    response = auth_client.put("/api/board", json=current)
    assert response.status_code == 422

    # DB unchanged
    after = auth_client.get("/api/board").json()
    assert after["columns"][0]["cardIds"] == []


def test_put_board_duplicate_cardid_rejected(auth_client: TestClient) -> None:
    current = auth_client.get("/api/board").json()
    current["cards"] = {
        "card-1": {"id": "card-1", "title": "A", "details": "."}
    }
    current["columns"][0]["cardIds"] = ["card-1"]
    current["columns"][1]["cardIds"] = ["card-1"]  # same id in two columns

    response = auth_client.put("/api/board", json=current)
    assert response.status_code == 422


def test_put_board_unreferenced_card_rejected(auth_client: TestClient) -> None:
    current = auth_client.get("/api/board").json()
    current["cards"] = {
        "card-orphan": {"id": "card-orphan", "title": "X", "details": "."}
    }
    # no column references card-orphan

    response = auth_client.put("/api/board", json=current)
    assert response.status_code == 422


def test_put_board_rejects_column_id_change(auth_client: TestClient) -> None:
    current = auth_client.get("/api/board").json()
    current["columns"][0]["id"] = "col-renamed"  # changing an id is not allowed

    response = auth_client.put("/api/board", json=current)
    assert response.status_code == 422


def test_put_board_rejects_extra_column(auth_client: TestClient) -> None:
    current = auth_client.get("/api/board").json()
    current["columns"].append(
        {"id": "col-extra", "title": "Extra", "cardIds": []}
    )

    response = auth_client.put("/api/board", json=current)
    assert response.status_code == 422


def test_db_persists_across_engine_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "persist.db"
    engine_a = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine_a)
    SessionA = sessionmaker(autocommit=False, autoflush=False, bind=engine_a, future=True)
    with SessionA() as db:
        seed_default_user(db)

    # mutate the board through the API while engine_a is bound
    def _override() -> Generator[Session, None, None]:
        s = SessionA()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _override
    try:
        client = TestClient(app)
        client.post("/api/auth/login", json={"username": "user", "password": "password"})
        data = client.get("/api/board").json()
        data["cards"] = {"card-x": {"id": "card-x", "title": "Persist", "details": "."}}
        data["columns"][0]["cardIds"] = ["card-x"]
        assert client.put("/api/board", json=data).status_code == 200
    finally:
        app.dependency_overrides.clear()

    engine_a.dispose()

    # Reopen with a fresh engine on the same file
    engine_b = make_engine(f"sqlite:///{db_path}")
    SessionB = sessionmaker(autocommit=False, autoflush=False, bind=engine_b, future=True)

    def _override_b() -> Generator[Session, None, None]:
        s = SessionB()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _override_b
    try:
        client = TestClient(app)
        client.post("/api/auth/login", json={"username": "user", "password": "password"})
        refetched = client.get("/api/board").json()
        assert refetched["cards"]["card-x"]["title"] == "Persist"
    finally:
        app.dependency_overrides.clear()
        engine_b.dispose()
