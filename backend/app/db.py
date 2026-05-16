from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Board, User
from app.schemas import empty_board

if TYPE_CHECKING:
    from sqlalchemy.pool import _ConnectionRecord  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "kanban.db"

SEED_USERNAME = "user"


def _resolve_db_path() -> Path:
    override = os.getenv("DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def make_engine(db_url: str | None = None) -> Engine:
    if db_url is None:
        path = _resolve_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{path}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine: Engine = make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def init_db(db_engine: Engine | None = None) -> None:
    Base.metadata.create_all(bind=db_engine or engine)


def seed_default_user(session: Session | None = None) -> None:
    owned = session is None
    db = session or SessionLocal()
    try:
        existing = db.query(User).filter(User.username == SEED_USERNAME).one_or_none()
        if existing is None:
            user = User(username=SEED_USERNAME)
            db.add(user)
            db.flush()
            db.add(Board(user_id=user.id, data=empty_board().model_dump_json()))
            db.commit()
    finally:
        if owned:
            db.close()


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
