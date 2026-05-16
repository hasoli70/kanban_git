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
- [ ] Test manuale: `scripts/start.*` → attendere "healthy" → `http://localhost:8000/` mostra hello world + risultato di `/api/health` (in attesa: Docker Desktop non in esecuzione sull'host)

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
- [ ] Verificare che le risorse statiche (`_next/static/...`, font, CSS) siano servite correttamente (test manuale via container, in attesa di Docker Desktop)
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
- [ ] **Backend**:
  - Configurare `starlette.middleware.sessions.SessionMiddleware`:
    - `secret_key` da env var `SESSION_SECRET`
    - `same_site="lax"`, `https_only=False` (true in prod futura), `http_only=True`, `max_age=86400` (1 giorno)
  - Modulo `backend/app/auth.py`:
    - Costanti `HARDCODED_USERNAME = "user"`, `HARDCODED_PASSWORD = "password"`
    - Endpoint `POST /api/auth/login` (body `{username, password}`):
      - Confronto diretto con le costanti
      - Se ok: `request.session["user"] = "user"` → 204 No Content
      - Se ko: 401
    - Endpoint `POST /api/auth/logout`: `request.session.clear()` → 204
    - Endpoint `GET /api/auth/me`: se `request.session.get("user")` → 200 `{user: "user"}`, altrimenti 401
    - Dipendenza FastAPI `require_auth` riutilizzabile
- [ ] **Frontend**:
  - Pagina `frontend/src/app/login/page.tsx` con form (username, password, submit) e gestione errori UX
  - In `frontend/src/app/page.tsx`: al mount, fetch `/api/auth/me`; se 401 → redirect a `/login`
  - Pulsante "Logout" nell'header del Kanban che chiama `/api/auth/logout` e redirige a `/login`
  - Tutte le fetch usano `credentials: "include"`
- [ ] Aggiornare `frontend/AGENTS.md` con la nuova pagina e il flusso auth

### Test
- [ ] Backend pytest:
  - `test_login_success`: credenziali corrette → 204 + cookie di sessione presente
  - `test_login_failure`: credenziali sbagliate → 401
  - `test_me_unauthenticated`: 401
  - `test_me_authenticated`: dopo login → 200 + `{user: "user"}`
  - `test_logout`: login → logout → `/api/auth/me` → 401
  - `test_cookie_flags`: ispezione del cookie set dopo login → contiene `HttpOnly` e `SameSite=Lax`
- [ ] Vitest: test della LoginPage (render, submit, gestione errore credenziali invalide)
- [ ] Playwright (flusso critico):
  - Visita `/` senza login → redirect a `/login`
  - Login corretto → board visibile
  - Logout → torno a `/login`

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
- [ ] Aggiungere `sqlalchemy` (sync) alle dipendenze
- [ ] Creare `backend/app/db.py`:
  - Engine SQLite verso `os.getenv("DB_PATH", "data/kanban.db")` (path relativo alla working dir del container)
  - `init_db()`: `CREATE TABLE IF NOT EXISTS` per `users` e `boards`
  - `seed_default_user()`: se non esiste user `user`, lo crea con board di default (5 colonne vuote come da Part 5)
  - Chiamare `init_db()` + `seed_default_user()` da FastAPI lifespan
- [ ] Creare `backend/app/models.py` (SQLAlchemy)
- [ ] Creare `backend/app/schemas.py` (Pydantic): `Card`, `Column`, `BoardData`
  - Validator su `BoardData`: ogni `cardId` referenziato nelle colonne deve esistere in `cards`; nessun cardId duplicato; nessun cardId orfano in `cards`
- [ ] Rotte (tutte protette da `require_auth`):
  - `GET /api/board` → `BoardData` dell'utente loggato
  - `PUT /api/board` → riceve `BoardData` completo, valida, salva (replace totale di `data`)

### Test (pytest)
- [ ] Fixture `tmp_db`: file SQLite temporaneo per ogni test, init + seed prima di ogni test
- [ ] `test_init_db`: tabelle create, user seed presente
- [ ] `test_get_board_unauthenticated`: 401
- [ ] `test_get_board_authenticated`: dopo login → 200 + struttura iniziale (5 colonne, 0 card)
- [ ] `test_put_board_persists`: PUT con nuovi dati → GET ritorna i nuovi dati
- [ ] `test_put_board_orphan_cardid`: PUT con `cardId` in colonna ma non in `cards` → 422
- [ ] `test_put_board_duplicate_cardid`: stesso `cardId` in due colonne → 422
- [ ] `test_db_persists_across_restart`: scrivi via PUT, ricrea engine, verifica che i dati siano ancora lì

### Criteri di successo
- `pytest` in `backend/` passa al 100%
- Riavviando il container, lo stato della board persiste (verifica manuale con `docker restart pm-app`)
- Il DB viene creato automaticamente al primo avvio

---

## Part 7: Frontend collegato al backend

Frontend usa le API reali invece dello state in-memory. La board è effettivamente persistente.

### Sotto-step
- [ ] Creare `frontend/src/lib/api.ts`:
  - `getBoard()`, `updateBoard(data)` con `fetch(..., { credentials: "include" })`
  - In dev mode usa `process.env.NEXT_PUBLIC_API_BASE`; in container mode usa path relativi (stessa origin)
- [ ] Modificare `KanbanBoard.tsx`:
  - Al mount: `getBoard()` per caricare lo stato iniziale (con loading skeleton/placeholder)
  - Ad ogni mutazione (drag/drop, add, delete, rename): update ottimistico dello state + chiamata `updateBoard()`
  - Gestione errore: se l'update fallisce, mostra banner di errore e fai rollback (mantieni il vecchio state)
  - Debounce di 500ms su `updateBoard()` per il rename colonna (evitare un PUT per ogni keystroke)
- [ ] Aggiornare `frontend/AGENTS.md` con la nuova architettura client/server

### Test
- [ ] Vitest: aggiornare i test dei componenti che dipendono da fetch — mockare l'API client (`vi.mock("@/lib/api")`)
- [ ] Backend pytest invariato
- [ ] Playwright (flusso critico): login → aggiungi card → reload pagina → la card è ancora visibile

### Criteri di successo
- Tutte le mutazioni (add, delete, move, rename) sono persistite nel DB
- Reload della pagina ricarica lo stato dal backend
- Riavvio del container preserva lo stato (grazie al volume di Part 2)
- I test passano

---

## Part 8: Connettività AI base (OpenRouter)

Verificare che il backend parli con OpenRouter e riceva risposte sensate.

### Sotto-step
- [ ] Creare `backend/app/ai.py` con `async call_openrouter(messages: list[dict]) -> dict`:
  - Endpoint `https://openrouter.ai/api/v1/chat/completions`
  - Header `Authorization: Bearer <OPENROUTER_API_KEY>`, modello `openai/gpt-oss-120b`
  - Timeout esplicito (30s)
  - Ritorna `{"content": str, "prompt_tokens": int, "completion_tokens": int}`
  - **Log strutturato** (modulo `logging`) di `prompt_tokens` e `completion_tokens` per ogni chiamata (no costi-cieci)
  - La chiave non finisce mai in log/eccezioni
- [ ] Endpoint `POST /api/ai/ping` (protetto): chiama l'AI con `"What is 2+2? Reply with just the number."` e ritorna `{reply}`
- [ ] Gestione errori: timeout / 4xx / 5xx da OpenRouter → 502 Bad Gateway con messaggio generico al client

### Test (pytest)
- [ ] `test_ai_ping_returns_4`: integration test "live" — skippato se `OPENROUTER_API_KEY` non è settata (`@pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"))`). Verifica che la risposta contenga `"4"`
- [ ] `test_ai_ping_unauthenticated`: 401
- [ ] `test_ai_logs_token_counts` (con mock di httpx): la chiamata produce una log entry con `prompt_tokens` e `completion_tokens`

### Criteri di successo
- POST `/api/ai/ping` ritorna risposta contenente "4"
- I log mostrano l'uso di token per ogni chiamata
- Errori upstream gestiti senza esporre dettagli interni

---

## Part 9: AI con Structured Outputs e contesto del Kanban

Endpoint chat AI riceve board corrente + storico + domanda utente; risponde con structured output (reply + opzionale `board_update`).

### Sotto-step
- [ ] Schema di Structured Output (Pydantic):
  ```
  class AIResponse:
    reply: str                       # testo per l'utente
    board_update: BoardData | None   # se presente, la nuova board completa proposta dall'AI
  ```
- [ ] **System prompt** (in `backend/app/ai_prompts.py`):
  - Descrive struttura di `BoardData`
  - Specifica che `board_update` deve essere `null` se non c'è modifica
  - Permette esplicitamente: aggiungere/eliminare/spostare card, rinominare colonne. **Vincola**: numero e ID delle colonne immutabili (le 5 di partenza)
- [ ] Endpoint `POST /api/ai/chat`:
  - Body: `{message: str, history: list[{role, content}]}`
  - Carica la board corrente dal DB
  - Costruisce messaggi: system prompt + board JSON come messaggio di sistema secondario + history + user message
  - Chiama OpenRouter con `response_format: {type: "json_schema", json_schema: ...}` per Structured Outputs
  - **Validazione regole esplicite** prima del save:
    1. `BoardData` valida (riusa i validator di Part 6)
    2. Il set di `column.id` deve essere identico a quello attualmente in DB (no colonne aggiunte/rimosse)
    3. I `column.title` possono cambiare (rinominare è permesso)
  - Se validazione fallisce → non salva, risponde `{reply, board_updated: false, validation_error: "..."}`
  - Se ok e `board_update != null` → salva nel DB, risponde `{reply, board_updated: true}`

### Test (pytest)
- [ ] `test_chat_simple_question` (mock AI): "Quante card ho in Backlog?" → reply, `board_updated == false`
- [ ] `test_chat_modify_board` (mock AI ritorna `board_update` valido): salva, GET `/api/board` riflette la modifica, `board_updated == true`
- [ ] `test_chat_rejects_column_id_change` (mock ritorna `board_update` con un `col.id` cambiato): risposta `board_updated: false` + `validation_error`, DB invariato
- [ ] `test_chat_rejects_orphan_cardid`: come sopra
- [ ] `test_chat_unauthenticated`: 401

### Criteri di successo
- L'AI risponde a domande sulla board
- Quando l'AI restituisce un `board_update` valido, il DB viene aggiornato e una successiva GET riflette la modifica
- Update che violano le regole vengono rifiutati senza corrompere lo stato

---

## Part 10: Sidebar AI chat nel frontend

Widget sidebar con chat AI completa. Quando l'AI modifica la board, la UI si refresha automaticamente.

### Sotto-step
- [ ] Creare `frontend/src/components/AIChatSidebar.tsx`:
  - Sidebar fissa a destra, toggleable (button "Chat" nell'header)
  - Lista messaggi (user/assistant) styled con palette del progetto
  - Input + pulsante "Invia"
  - Stato `history` in state locale (passato al backend ad ogni richiesta)
  - Indicatore di loading durante la chiamata
  - Quando la risposta ha `board_updated: true` → invoca callback `onBoardUpdate()` che ricarica via `getBoard()`
  - Gestione errore chiamata AI (banner)
  - Empty state ("Chiedimi qualcosa sulla tua board")
- [ ] Sollevare lo stato della board a un Context (`BoardContext`) condiviso tra `KanbanBoard` e `AIChatSidebar`, oppure passare callback dal parent. **Decisione**: Context, più pulito visto che cresce un secondo consumer
- [ ] Includere il sidebar in `app/page.tsx` accanto al `KanbanBoard`
- [ ] La history della chat è persa al refresh della pagina (decisione MVP: vedi Part 5)

### Test
- [ ] Vitest (mock `/api/ai/chat`):
  - Il messaggio utente compare nella lista
  - La risposta AI compare
  - Quando il mock ritorna `board_updated: true`, viene chiamato `getBoard()`
  - Quando ritorna errore, compare il banner di errore
- [ ] Playwright (flusso critico, skip se no API key):
  - Login → apri sidebar → invia "aggiungi una card 'Test AI' in Backlog"
  - Verifica che la risposta AI sia visibile in chat
  - Verifica che la card "Test AI" compaia nella colonna Backlog senza reload manuale

### Criteri di successo
- Chat AI funzionante senza reload
- Modifiche AI alla board visibili in UI senza refresh manuale
- App finale completa: login → board persistente con drag/drop → chat AI con structured output
- Tutti i test passano (unit, integration, E2E)

---

## Definition of Done complessiva

- [ ] `docker build` + `scripts/start.*` portano up l'app su `http://localhost:8000/`
- [ ] DB SQLite persiste su volume host, sopravvive a `docker stop`/`docker start`
- [ ] Login → board persistente → chat AI funzionante
- [ ] Suite test backend (pytest) e frontend (Vitest + Playwright per flussi critici) tutte verdi
- [ ] `ruff check backend/` pulito; ESLint frontend pulito
- [ ] `README` aggiornato con istruzioni di setup (dev mode + container mode)
- [ ] `frontend/AGENTS.md`, `backend/AGENTS.md`, `scripts/AGENTS.md`, `docs/DATABASE.md` allineati allo stato finale
- [ ] Nessuna chiave segreta committata; `.env` in `.gitignore`; `.env.example` presente
