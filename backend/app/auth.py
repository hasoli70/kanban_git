from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

HARDCODED_USERNAME = "user"
HARDCODED_PASSWORD = "password"

SESSION_KEY_USER = "user"

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class MeResponse(BaseModel):
    user: str


def require_auth(request: Request) -> str:
    user = request.session.get(SESSION_KEY_USER)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return user


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(payload: LoginRequest, request: Request, response: Response) -> Response:
    if payload.username != HARDCODED_USERNAME or payload.password != HARDCODED_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    request.session[SESSION_KEY_USER] = HARDCODED_USERNAME
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> Response:
    request.session.clear()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
def me(user: str = Depends(require_auth)) -> MeResponse:
    return MeResponse(user=user)
