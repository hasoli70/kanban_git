# Piano di esecuzione del progetto PM

Questo documento contiene il piano dettagliato per la realizzazione dell'MVP. Ogni parte ha:
- Sotto-step come checklist da spuntare durante l'esecuzione
- Test da scrivere/eseguire
- Criteri di successo concreti per considerare la parte completata

Convenzioni:
- Coding standards: vedi [AGENTS.md](../AGENTS.md) (keep it simple, no over-engineering, no emoji, root cause analysis)
- Backend: pytest + FastAPI TestClient. Frontend: Vitest (unit/integration) + Playwright (E2E per flussi critici)
- Tutti i path sono relativi alla root del progetto

---

## Workflow di sviluppo (dev mode vs container)

Per iterare velocemente senza rebuild Docker ad ogni modifica, lavoriamo in due modalità:

**Dev mode (sviluppo quotidiano)**
- Backend: `uvicorn app.main:app --reload --port 8000` (eseguito da `backend/`, con `.venv` locale gestita da `uv`)
- Frontend: `npm run dev` (porta 3000)
- Frontend punta al backend via env var `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- Backend abilita CORS **solo** quando env var `DEV_MODE=1`, accettando origin `http://localhost:3000`

**Container mode (run integrato / pre-release)**
- `scripts/start.*` builda l'immagine, monta il volume dati e avvia su `:8000`
- Frontend è servito staticamente dal backend (stessa origin → no CORS)
- DB SQLite persistito su volume host (vedi Part 2)

Le porte e le env var sono documentate in `.env.example` (da creare in Part 2).

---

## Part 1: Pianificazione

Arricchire il presente documento e creare `frontend/AGENTS.md` che descriva il codice esistente. Ottenere l'approvazione dell'utente prima di passare a Part 2.

### Sotto-step
- [x] Leggere [AGENTS.md](../AGENTS.md) e il codice esistente in `frontend/`
- [x] Arricchire `docs/PLAN.md` con sotto-step, test e criteri per tutte le parti
- [x] Creare `frontend/AGENTS.md` con descrizione del codice esistente
- [ ] Far rivedere e approvare il piano all'utente

### Criteri di successo
- `docs/PLAN.md` copre tutte le 10 parti con sotto-step concreti
- Esiste `frontend/AGENTS.md` che descrive struttura, componenti e convenzioni del frontend attuale
- L'utente ha dato approvazione esplicita per procedere

---

## Part 2: Scaffolding (Docker + FastAPI + script)

Infrastruttura: container Docker con volume persistente, backend FastAPI minimo, script di avvio/stop, healthcheck, linting. Il backend serve una pagina "hello world" e una rotta API di esempio.

### Sotto-step
- [x] Creare `backend/pyproject.toml` con:
  - Dipendenze runtime: `fastapi`, `uvicorn[standard]`, `httpx`, `python-dotenv`, `itsdangerous` (richiesta da SessionMiddleware, Part 4)
  - Dev dependencies: `pytest`, `ruff`
  - Configurazione `ruff` (line-length 100, target Python 3.12)
- [x] Creare `backend/app/main.py`:
  - Rotta `GET /api/health` → `{"status": "ok"}`
  - Mount `backend/static/` su `/` con `StaticFiles` (placeholder `index.html` che fa fetch a `/api/health`)
  - CORS abilitato solo se `os.getenv("DEV_MODE") == "1"`, allowed origin `http://localhost:3000`
- [x] Creare `backend/static/index.html` placeholder ("hello world" + chiamata `/api/health`)
- [x] Creare `data/.gitkeep` (directory per il DB SQLite, fuori dal codice)
- [x] Creare `.env.example` nella root con tutte le variabili documentate:
  - `OPENROUTER_API_KEY=`
  - `SESSION_SECRET=` (con istruzioni per generarla)
  - `DEV_MODE=0`
- [x] Verificare che `.env` sia in `.gitignore` (riga 130 esistente)
- [x] Creare `Dockerfile` nella root:
  - Base image `python:3.12-slim`
  - Installa `uv` con `pip install uv`
  - Copia `backend/pyproject.toml` + `backend/uv.lock` e installa con `uv sync --frozen --no-dev`
  - `EXPOSE 8000`
  - `HEALTHCHECK` via `python -c urllib.request...` (evita di installare `curl`)
  - `CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- [x] Creare `.dockerignore` (`node_modules`, `__pycache__`, `.venv`, `frontend/.next`, `frontend/out`, `data/*.db`, `.env`)
- [x] Creare script in `scripts/`:
  - `start.sh` (Mac/Linux) e `start.ps1` (Windows):
    - `docker build -t pm-app .`
    - `docker run -d --name pm-app -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" pm-app`
    - Loop di attesa healthcheck (`docker inspect --format '{{.State.Health.Status}}'`) → "healthy"
  - `stop.sh` e `stop.ps1`: `docker stop pm-app && docker rm pm-app`
- [x] Aggiornare `backend/AGENTS.md` con descrizione del backend
- [x] Aggiornare `scripts/AGENTS.md` con descrizione degli script

### Test
- [x] `backend/tests/test_health.py`: `TestClient` → `GET /api/health` ritorna 200 + `{"status": "ok"}`
- [x] `ruff check backend/` non rileva problemi
- [x] Test manuale: `scripts/start.*` → attendere "healthy" → `http://localhost:8000/` raggiungibile (test eseguito 2026-05-16, superato dal contenuto di Part 3: la home ora serve il Kanban invece del placeholder hello world)

### Criteri di successo
- `docker build` completa senza errori
- `scripts/start.*` avvia il container e `docker ps` mostra `healthy`
- `http://localhost:8000/api/health` → 200; la pagina hello world fa la chiamata API con successo
- Il volume `./data/` viene creato sull'host (verificabile da fuori il container)
- `pytest` e `ruff` passano
- `scripts/stop.*` ferma e rimuove il container

---

## Part 3: Integrazione del frontend statico

Build statico del frontend Next.js esistente, servito da FastAPI alla root `/`. Frontend continua a usare state in-memory (nessun backend collegato).

### Sotto-step
- [x] **Verifica preliminare** dei limiti di `output: "export"` con Next.js 16:
  - `frontend/next.config.ts` configurato con `output: "export"`
  - `npm run build` → "Generating static pages 4/4" senza warning bloccanti; font Google scaricati a build-time in `out/_next/static/media/` (Next.js li gestisce automaticamente con export)
  - Nessuna API route Next, nessun `next/image` con loader remoto: confermato
- [x] Aggiornare `Dockerfile` in multi-stage:
  - Stage 1 `frontend-build`: `node:20-slim`, `npm ci` in `frontend/`, `npm run build` → output in `frontend/out/`
  - Stage 2 `backend`: come Part 2, più `COPY --from=frontend-build /app/frontend/out/ ./static/` dentro `WORKDIR /app/backend` (previo `rm -rf static && mkdir static` per scartare il placeholder)
- [x] Sostituire il placeholder `backend/static/index.html` con i file generati dal build: il placeholder resta nel source tree (utile per dev mode standalone del backend) ma viene cancellato e rimpiazzato dal `COPY` nel Dockerfile
- [x] Verificare che le risorse statiche (`_next/static/...`, font, CSS) siano servite correttamente (test manuale 2026-05-16: drag/drop, add card, rename column, rimozione card ok)
- [x] Mantenere `/api/health` raggiungibile (FastAPI matcha le route specifiche prima del mount `/`)

### Test
- [x] Test backend esistente continua a passare (`pytest backend` → 1 passed)
- [ ] `npm run test:unit` continua a passare invariato (test su componenti, non sull'integrazione)
- [ ] Aggiornare `playwright.config.ts`: aggiungere variant che testa contro `http://localhost:8000/` quando env var `E2E_TARGET=container` è settata (default: dev su :3000)
- [ ] Test E2E contro container: `loads the kanban board` passa su `:8000`

### Criteri di successo
- `http://localhost:8000/` serve il Kanban Studio funzionante (drag/drop, add card, rename column)
- Nessun 404 sulle risorse statiche
- I test unit del frontend passano
- Il test E2E "loads the kanban board" passa contro il container

---

## Part 4: Login finto

Login con credenziali hardcoded `user` / `password`. **Decisione MVP**: il check delle credenziali resta hardcoded per sempre (no hashing, no tabella users coinvolta in auth). La tabella `users` esisterà solo per supportare multi-utente futuro e per dare un `user_id` alle board (Part 5-6).

### Sotto-step
- [x] **Backend**:
  - `SessionMiddleware` in [backend/app/main.py](../backend/app/main.py): `session_cookie="pm_session"`, `same_site="lax"` (in container) o `none` (DEV_MODE, per fetch cross-origin :3000→:8000), `https_only=False`, `max_age=86400`
  - Modulo [backend/app/auth.py](../backend/app/auth.py) con costanti `HARDCODED_USERNAME` / `HARDCODED_PASSWORD`, endpoint `/api/auth/login` (204), `/api/auth/logout` (204), `/api/auth/me` (200/401), dipendenza `require_auth`
- [x] **Frontend**:
  - [frontend/src/app/login/page.tsx](../frontend/src/app/login/page.tsx) con form e gestione errori UX (banner `role="alert"`)
  - [frontend/src/app/page.tsx](../frontend/src/app/page.tsx): client component, al mount `getMe()`, redirect `/login` se null
  - Pulsante "Logout" nell'header di [frontend/src/components/KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx) via prop `onLogout`
  - Tutte le fetch usano `credentials: "include"` via `apiFetch` in [frontend/src/lib/api.ts](../frontend/src/lib/api.ts)
- [x] Aggiornare `frontend/AGENTS.md` con la nuova pagina, struttura, e flusso auth

### Test
- [x] Backend pytest (7/7 in [backend/tests/test_auth.py](../backend/tests/test_auth.py)):
  - `test_login_success_sets_session_cookie`
  - `test_login_failure_returns_401`
  - `test_me_unauthenticated_returns_401`
  - `test_me_authenticated_returns_user`
  - `test_logout_clears_session`
  - `test_login_cookie_flags` (HttpOnly + SameSite=Lax)
- [x] Vitest: [frontend/src/app/login/page.test.tsx](../frontend/src/app/login/page.test.tsx) — submit ok, 401, network error (3/3)
- [x] Playwright (flusso critico) in [frontend/tests/auth.spec.ts](../frontend/tests/auth.spec.ts):
  - Visita `/` senza login → redirect a `/login`
  - Login corretto → board visibile
  - Login errato → banner errore, resta su `/login`
  - Logout → torno a `/login`
  - Aggiornato `playwright.config.ts`: spawn parallelo del backend con `DEV_MODE=1` e `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000` per il dev server

### Criteri di successo
- Senza login non si vede il Kanban
- Login con `user`/`password` mostra il Kanban
- Logout riporta a `/login`
- Cookie ha flag `HttpOnly` e `SameSite=Lax`
- Tutti i test passano

---

## Part 5: Modellazione del database

Definire lo schema, documentarlo, ottenere sign-off.

### Sotto-step
- [ ] Schema proposto:
  - Tabella `users` (id INTEGER PK AUTOINCREMENT, username TEXT UNIQUE NOT NULL, created_at TIMESTAMP). **Nessuna colonna password**: l'auth resta hardcoded (Part 4).
  - Tabella `boards` (id INTEGER PK AUTOINCREMENT, user_id INTEGER NOT NULL FK → users.id, data TEXT NOT NULL CHECK(json_valid(data)), updated_at TIMESTAMP). Un solo record per user nell'MVP; `data` è JSON serializzato con la stessa shape del `BoardData` del frontend.
- [ ] Scrivere `docs/DATABASE.md` con:
  - DDL SQL completo
  - Razionale (perché JSON in colonna invece di tabelle normalizzate: semplicità MVP, shape allineata al frontend, nessuna query parziale necessaria)
  - Nota su migrazioni: non serve un sistema di migration per l'MVP, basta `CREATE TABLE IF NOT EXISTS` allo startup
  - **Strategia di persistenza Docker**: file su `/app/data/kanban.db` (montato da volume host `./data/`), già configurato in Part 2
  - **Empty state seed**: l'utente seed `user` viene creato con board = 5 colonne (Backlog, Discovery, In Progress, Review, Done), 0 card. Coerente con [frontend/src/lib/kanban.ts](../frontend/src/lib/kanban.ts) ma senza i dati demo.
  - **Decisione storico chat AI**: gestito lato client e inviato ad ogni richiesta. Nessuna tabella `messages`.
  - Esempio di `data` JSON
- [ ] Ottenere approvazione esplicita dell'utente prima di Part 6

### Criteri di successo
- `docs/DATABASE.md` esiste, è chiaro, ed è stato approvato dall'utente

---

## Part 6: Backend API per il Kanban

Rotte API per leggere e aggiornare la board dell'utente loggato. Inizializzazione automatica del DB.

### Sotto-step
- [x] Aggiungere `sqlalchemy>=2.0` alle dipendenze runtime (vedi [backend/pyproject.toml](../backend/pyproject.toml))
- [x] [backend/app/db.py](../backend/app/db.py):
  - `make_engine()` con `connect_args={"check_same_thread": False}`; `PRAGMA journal_mode=WAL` + `PRAGMA foreign_keys=ON` via event listener
  - Default DB path = `<repo-root>/data/kanban.db` (override via `DB_PATH`); in container risolve a `/app/data/kanban.db` (mounted volume)
  - `init_db(engine?)`: `Base.metadata.create_all`
  - `seed_default_user(session?)`: se non esiste user `user`, lo crea con board di default (5 colonne vuote)
  - `get_session()` generator per FastAPI Depends, scope per-request
  - `init_db()` + `seed_default_user()` chiamati da FastAPI lifespan (vedi [backend/app/main.py](../backend/app/main.py))
- [x] [backend/app/models.py](../backend/app/models.py): SQLAlchemy 2.0 `User`, `Board` (FK CASCADE su user_id, UNIQUE → 1:1, CheckConstraint `json_valid(data)`)
- [x] [backend/app/schemas.py](../backend/app/schemas.py): Pydantic `Card`, `Column`, `BoardData` (`extra="forbid"`) + `model_validator` che vincola: chiave `cards[k]` == `card.id`, nessun cardId duplicato, nessun orphan in colonna, nessun unreferenced in cards
- [x] [backend/app/board.py](../backend/app/board.py): rotte protette da `require_auth`
  - `GET /api/board` → `BoardData`
  - `PUT /api/board` → valida payload (Pydantic) + verifica che il set di `column.id` sia immutabile vs DB (rename `title` permesso, add/remove colonne **non**), salva via replace di `data`

### Test (pytest, 9 nuovi in [backend/tests/test_board.py](../backend/tests/test_board.py))
- [x] Fixture `tmp_engine` + `client` + `auth_client`: SQLite temp con `dependency_overrides[get_session]`
- [x] `test_init_db_creates_user_and_empty_board`: tabelle create, user seed presente, 5 colonne vuote
- [x] `test_get_board_unauthenticated`: 401
- [x] `test_put_board_persists`: PUT con rinomina colonna + add card → GET conferma
- [x] `test_put_board_orphan_cardid_rejected`: 422
- [x] `test_put_board_duplicate_cardid_rejected`: 422
- [x] `test_put_board_unreferenced_card_rejected`: 422
- [x] `test_put_board_rejects_column_id_change`: 422
- [x] `test_put_board_rejects_extra_column`: 422
- [x] `test_db_persists_across_engine_restart`: PUT → dispose engine → riapri sullo stesso file → dati ancora presenti

### Criteri di successo
- [x] `pytest backend/` passa al 100% (16/16)
- [x] Riavviando il container, lo stato della board persiste (verifica manuale 2026-05-16: `docker restart pm-app` -> card "Pewrsist Test" ancora presente dopo reload)
- [x] Il DB viene creato automaticamente al primo avvio (lifespan startup)

---

## Part 7: Frontend collegato al backend

Frontend usa le API reali invece dello state in-memory. La board è effettivamente persistente.

### Sotto-step
- [x] Estendere [frontend/src/lib/api.ts](../frontend/src/lib/api.ts): `getBoard()`, `updateBoard(data)`; base URL via `NEXT_PUBLIC_API_BASE` (vuota in container)
- [x] Riscrivere [frontend/src/components/KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx):
  - State `BoardData | null`, fetch via `getBoard()` al mount, render "Loading board..." finche' non arriva
  - Optimistic update + rollback verso `lastSavedRef` su errore, con banner `role="alert"`
  - Debounce 500ms sul rename colonna; mutazioni non-rename flushano il timer pendente
  - Prop `onLogout` invariata da Part 4
- [x] Aggiornare [frontend/AGENTS.md](../frontend/AGENTS.md) con la nuova architettura client/server

### Test
- [x] Vitest: [frontend/src/components/KanbanBoard.test.tsx](../frontend/src/components/KanbanBoard.test.tsx) riscritto con `vi.mock("@/lib/api")`. 5 test: loading -> 5 colonne, debounce rename, add card optimistic, rollback su errore, banner load error. 11/11 totali pass
- [x] Backend pytest invariato (16/16)
- [x] Playwright [frontend/tests/kanban.spec.ts](../frontend/tests/kanban.spec.ts) "adds a card and persists it across page reload": add card -> reload -> card ancora visibile -> cleanup (delete)

### Criteri di successo
- [x] Tutte le mutazioni (add, delete, move, rename) sono persistite nel DB tramite PUT /api/board
- [x] Reload della pagina ricarica lo stato dal backend
- [x] Riavvio del container preserva lo stato (verifica manuale 2026-05-16: docker restart pm-app -> card sopravvissuta)
- [x] Test unit (Vitest) e backend (pytest) tutti verdi; E2E manda richieste reali al backend FastAPI in DEV_MODE

---

## Part 8: Connettività AI base (OpenRouter)

Verificare che il backend parli con OpenRouter e riceva risposte sensate.

### Sotto-step
- [x] Creare `backend/app/ai.py` con `async call_openrouter(messages: list[dict]) -> dict`:
  - Endpoint `https://openrouter.ai/api/v1/chat/completions`
  - Header `Authorization: Bearer <OPENROUTER_API_KEY>`, modello `openai/gpt-oss-120b`
  - Timeout esplicito (30s)
  - Ritorna `{"content": str, "prompt_tokens": int, "completion_tokens": int}`
  - **Log strutturato** (modulo `logging`) di `prompt_tokens` e `completion_tokens` per ogni chiamata (no costi-ciechi)
  - La chiave non finisce mai in log/eccezioni (`AIError` con messaggi generici)
- [x] Endpoint `POST /api/ai/ping` (protetto via `require_auth`): chiama l'AI con `"What is 2+2? Reply with just the number."` e ritorna `{reply}`
- [x] Gestione errori: timeout / 4xx / 5xx / payload malformato da OpenRouter → 502 Bad Gateway con messaggio generico al client

### Test (pytest, 8 nuovi in [backend/tests/test_ai.py](../backend/tests/test_ai.py))
- [x] `test_ai_ping_returns_4_live`: integration test "live" — skippato se `OPENROUTER_API_KEY` non è settata
- [x] `test_ai_ping_unauthenticated`: 401
- [x] `test_ai_ping_returns_upstream_content` (monkeypatch `call_openrouter`): 200 + `{reply}`
- [x] `test_ai_ping_maps_provider_error_to_502`: `AIError` → 502
- [x] `test_call_openrouter_missing_api_key_raises`: senza env var → `AIError`
- [x] `test_call_openrouter_logs_token_counts` (httpx `MockTransport`): log con `prompt_tokens=42 completion_tokens=7`, chiave assente dal log
- [x] `test_call_openrouter_timeout_raises_aierror`: `httpx.TimeoutException` → `AIError`, chiave assente
- [x] `test_call_openrouter_upstream_4xx_raises_aierror`: 429 → `AIError`

### Criteri di successo
- [x] POST `/api/ai/ping` mappato e protetto da auth (test verde con mock)
- [x] I log mostrano `prompt_tokens` e `completion_tokens` per ogni chiamata
- [x] Errori upstream gestiti senza esporre dettagli interni (la chiave non compare mai in log/eccezioni)
- [ ] Verifica live `test_ai_ping_returns_4_live` con `OPENROUTER_API_KEY` reale (richiede credito su OpenRouter)

---

## Part 9: AI con Structured Outputs e contesto del Kanban

Endpoint chat AI riceve board corrente + storico + domanda utente; risponde con structured output (reply + opzionale `board_update`).

### Sotto-step
- [x] Schema di Structured Output (Pydantic + JSON schema per OpenRouter `response_format`):
  - `ChatResponse` server-side: `reply: str`, `board_updated: bool`, `validation_error: str | None`
  - `AI_RESPONSE_SCHEMA` in [backend/app/ai_prompts.py](../backend/app/ai_prompts.py): JSON Schema strict con `{reply, board_update: null | BoardData}` (la validazione semantica fine resta lato server)
- [x] **System prompt** in [backend/app/ai_prompts.py](../backend/app/ai_prompts.py):
  - Descrive struttura di `BoardData`
  - Specifica che `board_update` deve essere `null` se non c'è modifica
  - Permette esplicitamente: aggiungere/eliminare/spostare card, rinominare colonne. **Vincola**: numero e ID delle colonne immutabili (le 5 di partenza)
- [x] Endpoint `POST /api/ai/chat` in [backend/app/ai.py](../backend/app/ai.py):
  - Body: `{message: str, history: list[{role, content}]}` (history filtrata a `user`/`assistant`)
  - Carica la board corrente dal DB
  - Costruisce messaggi: system prompt + board JSON come messaggio di sistema secondario + history + user message
  - Chiama OpenRouter con `response_format: {type: "json_schema", json_schema: AI_RESPONSE_SCHEMA}`
  - **Validazione regole esplicite** prima del save:
    1. `BoardData` valida (riusa validator di Part 6 in `app.schemas`)
    2. Lista di `column.id` deve coincidere esattamente con quella corrente in DB (anche stesso ordine)
    3. I `column.title` possono cambiare
  - Se validazione fallisce → non salva, risponde `{reply, board_updated: false, validation_error}`
  - Se ok e `board_update != null` → salva nel DB, risponde `{reply, board_updated: true}`
  - `AIError` upstream → HTTP 502

### Test (pytest, 8 nuovi in [backend/tests/test_ai_chat.py](../backend/tests/test_ai_chat.py))
- [x] `test_chat_unauthenticated`: 401
- [x] `test_chat_simple_question_no_board_update` (mock AI con `board_update: null`): `board_updated == false`, DB invariato
- [x] `test_chat_modify_board_persists` (mock con `board_update` valido): DB aggiornato, GET conferma
- [x] `test_chat_rejects_column_id_change`: `board_updated: false` + `validation_error`, DB invariato
- [x] `test_chat_rejects_orphan_cardid`: idem
- [x] `test_chat_handles_invalid_json_from_ai`: AI ritorna stringa non-JSON → `validation_error`, DB invariato
- [x] `test_chat_provider_error_maps_to_502`: `AIError` → 502
- [x] `test_chat_includes_system_and_board_messages`: verifica ordine messaggi (system / board JSON / history / user) e `response_format`

### Criteri di successo
- [x] L'AI risponde a domande sulla board (mock)
- [x] Quando l'AI restituisce un `board_update` valido, il DB viene aggiornato e una successiva GET riflette la modifica
- [x] Update che violano le regole vengono rifiutati senza corrompere lo stato

---

## Part 10: Sidebar AI chat nel frontend

Widget sidebar con chat AI completa. Quando l'AI modifica la board, la UI si refresha automaticamente.

### Sotto-step
- [x] Creare [frontend/src/components/AIChatSidebar.tsx](../frontend/src/components/AIChatSidebar.tsx):
  - Sidebar fissa a destra (`fixed right-0 top-0 h-screen max-w-sm`), aperta tramite button "Chat" nell'header di `KanbanBoard`, chiusa via button "Close" nell'header della sidebar
  - Lista messaggi (`user` bubble blu / `assistant` bubble grigia / `system` badge centrale per conferme e errori di validazione)
  - Input + pulsante "Send"; auto-focus dell'input all'apertura; auto-scroll a fondo lista
  - Stato `messages` in state locale (history passata al backend filtrata a `user`/`assistant`)
  - Indicatore "Thinking..." durante la chiamata
  - Quando la risposta ha `board_updated: true` → invoca callback `onBoardUpdated()` che il parent traduce in incremento di `reloadSignal` → `KanbanBoard` rifa `getBoard()`
  - Gestione errore chiamata AI: banner `role="alert"`
  - Empty state ("Ask me to add a card, move things between columns, or summarise what is in progress.")
- [x] **Deviazione dalla "Decisione: Context" del piano**: ho mantenuto lo state della board locale a `KanbanBoard` e introdotto solo una prop `reloadSignal: number` su `KanbanBoard` + callback `onBoardUpdated` su `AIChatSidebar`. Motivazione: `KanbanBoard` ha logica complessa interna (optimistic update, rollback, debounce, refs); spostarla su un Context era un refactor sproporzionato per un singolo consumer. La decisione è documentata in [../frontend/AGENTS.md](../frontend/AGENTS.md)
- [x] Includere `<AIChatSidebar>` in [frontend/src/app/page.tsx](../frontend/src/app/page.tsx) accanto a `<KanbanBoard>`; il parent possiede `chatOpen` e `boardReloadSignal`
- [x] La history della chat è persa al refresh della pagina (decisione MVP: vedi Part 5)

### Test
- [x] Vitest [frontend/src/components/AIChatSidebar.test.tsx](../frontend/src/components/AIChatSidebar.test.tsx) (8 test, mock `chatAI`):
  - Render nullo se `open=false`
  - Empty state quando aperta
  - Il messaggio utente + reply assistant compaiono nella lista
  - `onBoardUpdated` viene chiamato quando il mock ritorna `board_updated: true` + badge "Board updated."
  - `validation_error` viene mostrato senza chiamare `onBoardUpdated`
  - Su `ApiError` compare il banner `role="alert"`
  - La history di una conversazione successiva viene inviata correttamente al backend
  - `onClose` viene invocato dal pulsante Close
- [x] Playwright [frontend/tests/ai-chat.spec.ts](../frontend/tests/ai-chat.spec.ts):
  - Aprire/chiudere la sidebar (non richiede chiave API)
  - **Skip se no `OPENROUTER_API_KEY`**: chat live -> "Add a card titled '...' to Backlog" -> attesa di "Board updated." -> verifica che la card compaia in Backlog senza reload + cleanup

### Criteri di successo
- [x] Chat AI funzionante senza reload (mock confermano flusso completo)
- [x] Modifiche AI alla board visibili in UI senza refresh manuale (via `reloadSignal`)
- [x] App finale completa: login -> board persistente con drag/drop -> chat AI con structured output
- [x] Tutti i test passano (Vitest 19/19, backend pytest 31/31 + 1 skip live ping, ESLint clean, Next.js build ok)
- [ ] Verifica live Playwright `adds a card via the AI` con chiave OpenRouter reale (richiede credito)

---

## Definition of Done complessiva

- [x] `docker build` + `scripts/start.*` portano up l'app su `http://localhost:8000/` (Part 2/3, verificato 2026-05-16)
- [x] DB SQLite persiste su volume host, sopravvive a `docker stop`/`docker start` (verificato cross-restart 2026-05-16)
- [x] Login → board persistente → chat AI funzionante (con mock; live verificabile con `OPENROUTER_API_KEY`)
- [x] Suite test backend (pytest 31/31 + 1 skip live) e frontend (Vitest 19/19, Playwright auth+kanban+ai non-live)
- [x] `ruff check backend/` pulito; ESLint frontend pulito
- [ ] `README` aggiornato con istruzioni di setup (dev mode + container mode)
- [x] `frontend/AGENTS.md`, `backend/AGENTS.md`, `scripts/AGENTS.md`, `docs/DATABASE.md` allineati allo stato finale
- [x] Nessuna chiave segreta committata; `.env` in `.gitignore`; `.env.example` presente
