# Worklog

Registro cronologico delle sessioni di lavoro sul progetto. Per il piano completo vedi [PLAN.md](PLAN.md); per le convenzioni vedi [../AGENTS.md](../AGENTS.md).

Convenzioni:
- Una entry per sessione/macro-step, in ordine cronologico inverso (più recente in cima)
- Ogni entry indica: parte del piano, commit di riferimento, cosa è stato fatto, cosa resta in sospeso

---

## 2026-05-16 — Part 7: Frontend collegato al backend

**Commit:** (vedi `git log`)

**Fatto:**
- [frontend/src/lib/api.ts](../frontend/src/lib/api.ts) esteso con `getBoard()` e `updateBoard(data)`. Mantiene `credentials: "include"` via `apiFetch`
- [frontend/src/components/KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx) riscritto: state `BoardData | null`, fetch al mount, optimistic update con rollback (`lastSavedRef`) su errore, debounce 500ms sul rename. Banner di errore `role="alert"` quando una PUT fallisce. Mutazioni non-rename flushano il timer pendente prima di applicare la nuova mutazione (per evitare race tra rename in pending e altre mutazioni)
- [frontend/src/components/KanbanBoard.test.tsx](../frontend/src/components/KanbanBoard.test.tsx) riscritto con `vi.mock("@/lib/api")` (factory inline per `ApiError`). 5 test: loading -> 5 colonne, debounce rename, add card optimistic, rollback su errore, banner load error
- Decisione: niente `vi.useFakeTimers()` per il test del debounce (causava timeout sui test successivi). Uso `waitFor` con timeout 1500ms per aspettare il debounce reale
- [frontend/tests/kanban.spec.ts](../frontend/tests/kanban.spec.ts): rimosso il test "moves a card between columns" (dipendeva da `card-card-1` demo non piu' esistente). Aggiunto "adds a card and persists it across page reload" come flusso critico (login -> add -> reload -> visibile -> cleanup)
- [frontend/AGENTS.md](../frontend/AGENTS.md) aggiornato: nuova architettura client/server, sezione optimistic update + rollback + debounce, `initialData` marcato come non piu' usato in produzione
- Test totali: Vitest 11/11, backend pytest 16/16, Next.js build ok (3 route: /, /login, /_not-found)

**In sospeso:**
- Verifica manuale: `docker restart pm-app` -> rilancia il container, login, vedi la card persistita (richiede Docker Desktop)
- Esecuzione E2E Playwright completa (richiede `npx playwright install` per i browser)

---

## 2026-05-16 — Part 6: Backend API per il Kanban (DB + endpoints)

**Commit:** (vedi `git log`)

**Fatto:**
- Aggiunta dipendenza `sqlalchemy>=2.0` (vedi `backend/pyproject.toml` + `uv.lock`)
- [backend/app/db.py](../backend/app/db.py): engine SQLite (WAL + foreign_keys ON via listener), default path `<repo-root>/data/kanban.db` con override `DB_PATH`, `init_db`, `seed_default_user`, `get_session` generator
- [backend/app/models.py](../backend/app/models.py): SQLAlchemy 2.0 `User`/`Board`. FK CASCADE, `user_id UNIQUE` (1:1), `CheckConstraint("json_valid(data)")`
- [backend/app/schemas.py](../backend/app/schemas.py): Pydantic `Card`/`Column`/`BoardData` con validator (no orphan/duplicate/unreferenced, key==id)
- [backend/app/board.py](../backend/app/board.py): `GET/PUT /api/board` con `require_auth`; PUT enforce immutabilità del set di `column.id` (rename permesso, add/remove no)
- [backend/app/main.py](../backend/app/main.py): lifespan async che chiama `init_db()` + `seed_default_user()` allo startup; include `board_router`
- [backend/tests/test_board.py](../backend/tests/test_board.py): 9 test con fixture `tmp_engine` + `dependency_overrides`. Coperti: init+seed, auth, put/get persistenza, validator semantici, immutabilità colonne, persistenza cross-restart
- Pytest totale: 16/16. Ruff clean.

**Decisioni applicative:**
- `seed_default_user` resta idempotente: se l'utente esiste già non fa nulla. La board di default è la `empty_board()` di `schemas.py` (5 colonne vuote, nessuna card)
- DB path computato come absolute path da `__file__` per funzionare sia in dev che in container senza configurazione

**In sospeso:**
- Test manuale: `docker restart pm-app` conferma persistenza della board sul volume host (richiede Docker Desktop). Il volume era già configurato in Part 2

---

## 2026-05-16 — Part 5: Schema DB (DATABASE.md)

**Commit:** `4ee1f7e`

**Fatto:**
- [docs/DATABASE.md](DATABASE.md) con DDL `users` + `boards`, razionale "JSON in colonna" vs normalizzato, strategia persistenza Docker (volume `data/`), seed iniziale (5 colonne vuote), decisione "chat AI history lato client", esempio JSON
- Vincoli semantici documentati: no orphan/duplicate/unreferenced cardId, colonne immutabili (rename only)
- Approvato esplicitamente dall'utente prima di Part 6

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
