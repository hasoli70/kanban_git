# Worklog

Registro cronologico delle sessioni di lavoro sul progetto. Per il piano completo vedi [PLAN.md](PLAN.md); per le convenzioni vedi [../AGENTS.md](../AGENTS.md).

Convenzioni:
- Una entry per sessione/macro-step, in ordine cronologico inverso (più recente in cima)
- Ogni entry indica: parte del piano, commit di riferimento, cosa è stato fatto, cosa resta in sospeso

---

## 2026-05-16 — Verifica manuale end-to-end Parts 2-4 (container Docker)

**Eseguita su Docker Desktop / Windows 11. Risultato: tutto ok.**

Step verificati:
- `scripts/start.ps1` builda l'immagine multi-stage e attende `healthy` con successo
- `http://localhost:8000/` → auth-gate → redirect a `/login`
- Login con `user`/`password` → board Kanban con 5 colonne servita correttamente (static export di Next.js + font + CSS dal container)
- Drag/drop card tra colonne, add card, rimozione card, rename colonna: tutto funzionante
- Logout dall'header → torno a `/login`
- Login con password errata → banner `role="alert"` "Invalid username or password.", resta su `/login`
- `scripts/stop.ps1` ferma e rimuove il container

**Nota:** persistenza del board non ancora attiva (arriva in Part 6/7). Reload pagina = stato iniziale demo.

---

## 2026-05-16 — Part 4: Login finto

**Commit:** `e5a81eb`

**Fatto:**
- Backend: `SessionMiddleware` in [backend/app/main.py](../backend/app/main.py) (`cookie pm_session`, `SameSite=Lax`; `None` in `DEV_MODE` per fetch cross-origin :3000→:8000)
- Backend: [backend/app/auth.py](../backend/app/auth.py) con `/api/auth/{login,logout,me}` + dipendenza `require_auth`
- Backend: [backend/tests/test_auth.py](../backend/tests/test_auth.py) — 7 test, tutti pass (login ok/fail, me auth/unauth, logout, cookie flags)
- Frontend: [frontend/src/lib/api.ts](../frontend/src/lib/api.ts) con `apiFetch` (`credentials: "include"`) + `login`/`logout`/`getMe`; base URL via `NEXT_PUBLIC_API_BASE`
- Frontend: [frontend/src/app/login/page.tsx](../frontend/src/app/login/page.tsx) (form + banner `role="alert"`)
- Frontend: [frontend/src/app/page.tsx](../frontend/src/app/page.tsx) convertita a client component con auth-gate (`getMe` al mount → redirect `/login` se 401)
- Frontend: `<KanbanBoard>` accetta prop opzionale `onLogout` e renderizza un button nell'header
- Frontend test: Vitest per LoginPage (3 test, tutti pass)
- Frontend test: Playwright `tests/auth.spec.ts` per il flow auth + `tests/kanban.spec.ts` aggiornato con `loginAsTestUser` in `beforeEach`
- Frontend test: `playwright.config.ts` ora spawna sia il backend FastAPI (con `DEV_MODE=1`) che il Next.js dev server, con `NEXT_PUBLIC_API_BASE` settato per il frontend

**In sospeso:**
- Test E2E Playwright eseguito automaticamente (richiede backend FastAPI raggiungibile)
- Verifica manuale fine-to-end del flow login → board → logout via container (richiede Docker Desktop avviato)

---

## 2026-05-16 — Part 3: Integrazione frontend statico

**Commit:** `6ad5437`

**Fatto:**
- [frontend/next.config.ts](../frontend/next.config.ts) configurato con `output: "export"`
- Verifica preflight: `npm run build` genera `frontend/out/` con `index.html`, `_next/static/...`, font Google embeddati in `_next/static/media/`. Niente warning bloccanti
- Dockerfile riscritto come multi-stage: Stage 1 `node:20-slim` builda il frontend (`npm ci` + `npm run build`); Stage 2 `python:3.12-slim` rimpiazza `static/` col bundle del frontend (`rm -rf static && mkdir static` + `COPY --from=frontend-build`)
- Backend `/api/health` resta raggiungibile (route specifica matchata prima del mount `/`)
- `backend/static/index.html` placeholder resta nel source per testing standalone del backend (sostituito dal `COPY` nel container)

**In sospeso:**
- Test manuale via Docker: aprire `http://localhost:8000/` e verificare drag/drop, add card, rename column (richiede Docker Desktop)
- E2E variant `E2E_TARGET=container` per testare contro `:8000`

---

## 2026-05-16 — Part 2: Scaffolding Docker + FastAPI

**Commit:** `1ce9bce`

**Fatto:**
- `backend/`: FastAPI app con `GET /api/health`, mount static (`backend/static/index.html` placeholder), CORS condizionale solo se `DEV_MODE=1`
- `backend/pyproject.toml` + `uv.lock` (deps runtime: `fastapi`, `uvicorn[standard]`, `httpx`, `python-dotenv`, `itsdangerous`; dev: `pytest`, `ruff`)
- `backend/tests/test_health.py` — 1 test, pass
- Configurazione `ruff` (line-length 100, target `py312`); `ruff check backend` pulito
- `Dockerfile` multi-step (`python:3.12-slim` + `uv sync --frozen --no-dev`), `HEALTHCHECK` via `urllib.request` (evita di installare `curl`)
- `.dockerignore` (esclude `node_modules`, `.venv`, `__pycache__`, `frontend/.next`, `frontend/out`, `data/*.db`, `.env`, ecc.)
- `.env.example` con `OPENROUTER_API_KEY`, `SESSION_SECRET`, `DEV_MODE`
- Script `scripts/start.{sh,ps1}` e `scripts/stop.{sh,ps1}` con loop di attesa healthcheck
- `data/.gitkeep` per il volume SQLite (sarà usato da Part 6)
- AGENTS.md aggiornati (`backend/`, `scripts/`)

**In sospeso:**
- Test manuale: `scripts/start.*` → `:8000` → page hello world + `/api/health` (richiede Docker Desktop)

---

## 2026-05-16 — Part 1: Pianificazione

**Commit:** `9f1ed98`

**Fatto:**
- [docs/PLAN.md](PLAN.md) arricchito con tutte le 10 parti, sotto-step a checkbox, test e criteri di successo
- Documentato workflow dev mode vs container mode
- Decisione MVP: credenziali login hardcoded per sempre, history chat AI lato client, board come JSON in colonna unica
- Creato [../frontend/AGENTS.md](../frontend/AGENTS.md) con descrizione completa di struttura, componenti, palette, convenzioni del frontend esistente
- Creato stub `backend/AGENTS.md` e `scripts/AGENTS.md` (poi riempiti in Part 2)
