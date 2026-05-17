from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Load .env from the repo root for dev-mode standalone runs. In container the values
# come from `docker run --env-file`; load_dotenv does not override existing env vars,
# so this is a no-op there.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from app.ai import router as ai_router  # noqa: E402
from app.auth import router as auth_router  # noqa: E402
from app.board import router as board_router  # noqa: E402
from app.db import init_db, seed_default_user  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_default_user()
    yield


app = FastAPI(title="PM Backend", version="0.1.0", lifespan=lifespan)

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-insecure-secret-change-me")
DEV_MODE = os.getenv("DEV_MODE") == "1"

# In dev mode the Next.js dev server (port 3000) calls the backend (port 8000) cross-origin.
# SameSite=Lax would block the session cookie on those XHR/fetch requests, so we switch to
# None for dev. In container/prod the frontend is served same-origin: Lax is correct.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="pm_session",
    same_site="none" if DEV_MODE else "lax",
    https_only=False,
    max_age=86400,
)

if DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(board_router)
app.include_router(ai_router)


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
