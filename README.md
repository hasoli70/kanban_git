# PM — Kanban + AI chat (MVP)

Single-user Kanban board with an AI chat sidebar that can read and modify the board.
Next.js (static export) served by FastAPI, SQLite for persistence, OpenRouter for the LLM.

For the design and execution plan see [docs/PLAN.md](docs/PLAN.md); for the DB schema see [docs/DATABASE.md](docs/DATABASE.md).

## Prerequisites

- Docker Desktop (container mode), **or** Python 3.12 + Node.js 20 with [`uv`](https://docs.astral.sh/uv/) (dev mode)
- An OpenRouter API key — free tier works (https://openrouter.ai/keys)

## Setup

```sh
cp .env.example .env
```

Edit `.env`:
- `OPENROUTER_API_KEY` — your key (the AI chat requires it; the board itself works without)
- `SESSION_SECRET` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- Leave `DEV_MODE=0` for container mode

## Container mode (run the app)

```sh
# Mac/Linux
./scripts/start.sh
# Windows
./scripts/stop.ps1; ./scripts/start.ps1
```

The script builds the image (multi-stage: Node builds the static frontend, Python runs FastAPI) and waits for the Docker healthcheck.

- App: http://localhost:8000
- Default credentials: `user` / `password`
- SQLite DB persisted to `./data/kanban.db` on the host

Stop with `./scripts/stop.{sh,ps1}`.

## Dev mode (fast iteration, no Docker)

Two terminals.

Backend (port 8000):
```sh
cd backend
uv sync
DEV_MODE=1 uv run uvicorn app.main:app --reload --port 8000
```

The backend auto-loads the root `.env` on startup (existing env vars are not
overridden), so no extra step is needed for `OPENROUTER_API_KEY` /
`SESSION_SECRET`.

Frontend (port 3000):
```sh
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

In dev mode the backend allows CORS from `http://localhost:3000`. Open http://localhost:3000.

## Tests

Backend (pytest):
```sh
cd backend
uv run pytest
uv run ruff check .
```

Frontend (Vitest + Playwright):
```sh
cd frontend
npm run test:unit
npm run test:e2e   # requires `npx playwright install` once
npm run lint
```

The live OpenRouter tests are auto-skipped when `OPENROUTER_API_KEY` is not set.

## PWA

Open the app in Chrome/Edge and use the install button in the URL bar to install it as a standalone app. No service worker (no offline support).
