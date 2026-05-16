from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_session
from app.models import Board, User
from app.schemas import BoardData

router = APIRouter(prefix="/api/board", tags=["board"])

# Module-level dependency markers to avoid Depends() in argument defaults (ruff B008).
_DB = Depends(get_session)
_AUTH = Depends(require_auth)


def _load_user_board(session: Session, username: str) -> Board:
    user = session.query(User).filter(User.username == username).one_or_none()
    if user is None or user.board is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="user has no board (seed missing)",
        )
    return user.board


@router.get("", response_model=BoardData)
def get_board(
    user: str = _AUTH,
    session: Session = _DB,
) -> BoardData:
    board = _load_user_board(session, user)
    return BoardData.model_validate_json(board.data)


@router.put("", response_model=BoardData)
def put_board(
    payload: BoardData,
    user: str = _AUTH,
    session: Session = _DB,
) -> BoardData:
    board = _load_user_board(session, user)
    current = BoardData.model_validate_json(board.data)

    current_ids = {c.id for c in current.columns}
    new_ids = {c.id for c in payload.columns}
    if current_ids != new_ids or len(current.columns) != len(payload.columns):
        raise HTTPException(
            status_code=422,
            detail="column ids cannot be added or removed (rename only)",
        )

    board.data = payload.model_dump_json()
    session.commit()
    session.refresh(board)
    return payload
