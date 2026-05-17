from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session, make_engine, seed_default_user
from app.main import app
from app.models import Base


@pytest.fixture
def tmp_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    db_path = tmp_path / "test.db"
    engine = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)

    TmpSession = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
    with TmpSession() as db:
        seed_default_user(db)

    def _override_get_session() -> Generator[Session, None, None]:
        db = TmpSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield engine
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(tmp_engine: Engine) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 204
    return client
