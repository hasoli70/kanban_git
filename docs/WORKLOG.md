# Worklog

Registro cronologico delle sessioni di lavoro sul progetto. Per il piano completo vedi [PLAN.md](PLAN.md); per le convenzioni vedi [../AGENTS.md](../AGENTS.md).

Convenzioni:
- Una entry per sessione/macro-step, in ordine cronologico inverso (più recente in cima)
- Ogni entry indica: parte del piano, commit di riferimento, cosa è stato fatto, cosa resta in sospeso

---

## 2026-05-17 — PWA: icone PNG raster per soddisfare Chrome install criteria

**Commit:** (in arrivo)

**Contesto:** dopo l'aggiunta del service worker, in Chrome DevTools -> Application -> Manifest comparivano errori bloccanti:
- `icon http://localhost:8000/icon.svg failed to load`
- `icon http://localhost:8000/icon-maskable.svg failed to load`
- `Most operating systems require square icons. Please include at least one square icon in the array.`

Chrome desktop attuale richiede icone PNG raster con `sizes` esplicito (192x192 e 512x512). Le SVG con `sizes: "any"` non bastano piu'.

**Fatto:**
- Generate 3 PNG con PowerShell + `System.Drawing` (no nuove dipendenze, no tool esterni):
  - [frontend/public/icon-192.png](../frontend/public/icon-192.png) — 192x192, purpose `any`
  - [frontend/public/icon-512.png](../frontend/public/icon-512.png) — 512x512, purpose `any`
  - [frontend/public/icon-512-maskable.png](../frontend/public/icon-512-maskable.png) — 512x512, purpose `maskable`, safe-area ~80% centrata
  - Tutte raffigurano: sfondo navy `#032147` + barra giallo accent in alto + 4 colonne kanban (blue/purple/yellow/gray, altezze decrescenti)
- [frontend/public/manifest.webmanifest](../frontend/public/manifest.webmanifest): array `icons` aggiornato con le 3 PNG + SVG mantenuta come fallback
- `npm run build` ok; `out/icon-192.png` (1133b), `out/icon-512.png` (4993b), `out/icon-512-maskable.png` (4710b), `out/manifest.webmanifest` (790b)

**Decisione: niente Pillow / niente conversione SVG -> PNG**
- `System.Drawing` e' built-in su Windows PowerShell (no `pip install`, no node tool)
- Le PNG ridisegnano l'artwork da zero (rettangoli colorati) invece di rasterizzare la SVG: piu' semplice, niente dipendenze, identico risultato visivo
- Tradeoff: se cambia il design SVG, vanno rigenerate a mano via script PowerShell. Si potrebbe spostare lo script in `scripts/gen-icons.ps1` quando avra' senso

**In sospeso (verifica mobile/install):**
- Test PWA install in Chrome desktop (richiede rebuild container + hard reload)
- Test PWA install su mobile: localhost non e' raggiungibile, serve HTTPS. Due strade documentate in chat:
  - LAN HTTP (`http://<lan-ip>:8000`): si vede ma non si installa (Chrome mobile richiede HTTPS)
  - HTTPS tunnel (es. `cloudflared tunnel --url http://localhost:8000`): installabile via menu "Aggiungi a schermata Home"

---

## 2026-05-17 — PWA: service worker + offline fallback

**Commit:** (in arrivo)

**Contesto:** la sessione PWA precedente aveva esplicitamente lasciato il service worker come work item futuro. L'utente ora vuole "che sia una PWA" piena -> aggiungo SW con offline fallback.

**Fatto:**
- [frontend/public/sw.js](../frontend/public/sw.js): SW custom (no Workbox / next-pwa). Strategia stale-while-revalidate per same-origin GET requests; cache `kanban-v1`; bypass `/api/*` (no cache di dati/sessione); precache di `manifest.webmanifest`, `icon.svg`, `icon-maskable.svg`, `offline.html`; `skipWaiting()` + `clients.claim()` per attivazione immediata
- [frontend/public/offline.html](../frontend/public/offline.html): pagina statica self-contained (no font/asset esterni), brand-aligned con la palette (navy/giallo), pulsante "Retry" che fa `location.reload()`. Servita per le `navigate` requests quando offline e senza cache
- [frontend/src/components/ServiceWorkerRegistration.tsx](../frontend/src/components/ServiceWorkerRegistration.tsx): client component che fa `navigator.serviceWorker.register("/sw.js")` al mount. Skippa la registrazione fuori da `https://` se l'host non e' `localhost`/`127.0.0.1` (browser non lo permetterebbero comunque)
- [frontend/src/app/layout.tsx](../frontend/src/app/layout.tsx): include `<ServiceWorkerRegistration />` accanto a `{children}` nel `<body>`
- [frontend/AGENTS.md](../frontend/AGENTS.md): sezione PWA aggiornata coi nuovi sorgenti e istruzioni per testare il SW da DevTools

**Verifiche:**
- `npm run build` ok: `out/sw.js` (1607b), `out/offline.html` (1647b), `out/manifest.webmanifest` (548b), icone presenti
- `npm run lint` clean, `npm run test:unit` 19/19 invariati
- Verifica live nel container/browser non eseguita in questa sessione (Docker Desktop non era running)

**Decisioni:**
- Niente Workbox, niente `next-pwa`: il SW e' ~50 righe, gestibile senza altre dipendenze. Bisogna ricordarsi di bumpare `CACHE_NAME` (es. `kanban-v2`) quando cambia la shape degli asset cached
- `/api/*` mai cachato: la session cookie e' http-only ma le risposte (board content) NON devono finire in cache disco lato browser. Le richieste passano direttamente a fetch nativo (return early dal handler)
- Stale-while-revalidate, non network-first: con il static export Next.js gli asset hashati (`_next/static/*`) sono immutabili -> cache illimitata e' safe. Per l'index HTML invece il prossimo deploy aggiorna in background; l'utente vede la versione vecchia per una visita poi quella nuova

**In sospeso:**
- Verifica install manuale (Chrome -> Install) -> finestra standalone
- DevTools -> Network -> Offline reload -> deve mostrare `offline.html`
- Bump di `CACHE_NAME` al prossimo deploy con cambi UI rilevanti

---

## 2026-05-17 — Auto-load .env in dev + null-content guard

**Commit:** (in arrivo)

**Contesto:** durante la verifica live AI in dev standalone era emerso che il backend non chiamava `load_dotenv()`. Funzionava in container (`docker run --env-file`) ma non in dev mode senza pre-export delle env var. Inoltre il free tier `openai/gpt-oss-120b:free` aveva ritornato `content: null` causando un 500 non gestito.

**Fatto:**
- [backend/app/main.py](../backend/app/main.py): aggiunto `load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")` a livello modulo, prima degli import di `app.*` (i router leggono env var a import time). `load_dotenv` non sovrascrive le var gia' presenti -> in container e' un no-op
- [backend/app/ai.py](../backend/app/ai.py): `call_openrouter` ora verifica `isinstance(content, str)` e solleva `AIError("AI provider returned an empty response")` se manca. Mappa al 502 invece che 500. Motivo: il free tier ritorna sporadicamente `choices[0].message.content = null`
- [backend/tests/test_ai.py](../backend/tests/test_ai.py): nuovo test `test_call_openrouter_null_content_raises_aierror` con `httpx.MockTransport`
- [README.md](../README.md): aggiunta nota "backend auto-loads root `.env` on startup, no extra step needed"
- Verifica live ripetuta in shell pulita (env unset): uvicorn parte, `POST /api/ai/chat` -> 200 con `board_updated=true`, card creata e poi rimossa

**Test:** 33/33 backend pass, ruff pulito. La modifica e' non-breaking: produzione (container) si comporta esattamente come prima

---

## 2026-05-17 — Verifica live AI chat (dev mode)

**Eseguita senza Docker (Docker Desktop non era running). Risultato: OK.**

Procedura:
- Backend avviato standalone (`backend/.venv/Scripts/uvicorn.exe app.main:app --port 8765`) con env loaded da `.env` (`OPENROUTER_API_KEY`, `SESSION_SECRET`, `DEV_MODE=1`)
- Login `user`/`password` -> cookie sessione
- `POST /api/ai/chat` con messaggio "Please add a new card titled 'Live Smoke 2026-05-17' ... to the Backlog column."
- Risposta in **17.1s**: `{board_updated: true, reply: "Added the new card 'Live Smoke 2026-05-17' to the Backlog column.", validation_error: null}`
- `GET /api/board` post-chat: card `card-live-smoke` presente in `col-backlog`
- Cleanup via PUT (rimossa la card, board ripristinata a 2 card pre-esistenti)

**Conferma che:**
- Modello free-tier `openai/gpt-oss-120b:free` rispetta correttamente lo schema strict di structured output di Part 9
- La validazione semantica (`schemas.py` + check column-id immutabili) accetta l'update proposto dall'AI
- Il save su DB e' atomico (board count torna a +1 dopo la chiamata, persistito su `data/kanban.db`)
- Latenza ragionevole (~17s) per il free tier

**Gotcha trovato (dev mode):**
- Il backend NON chiama `load_dotenv()` in main.py. In container i valori arrivano via `docker run --env-file .env`. In dev standalone, lanciare `uvicorn ...` senza prima esportare le var di `.env` -> `/api/ai/chat` ritorna 500 `"AI provider is not configured"`. Il [README.md](../README.md) dovrebbe esplicitarlo (es. "exporta le var di `.env` prima di lanciare uvicorn, oppure usa `uv run --env-file ../.env ...`"), oppure il backend dovrebbe chiamare `load_dotenv()` all'avvio per uniformare dev/container

**In sospeso:**
- Verifica end-to-end full nel container (Docker Desktop non attivo durante questa sessione)
- Verifica install PWA in Chrome

---

## 2026-05-17 — README di setup (chiude la Definition of Done)

**Commit:** (in arrivo)

**Fatto:**
- [README.md](../README.md): istruzioni minimal per container mode (`scripts/start.*` + `.env`) e dev mode (uvicorn + npm run dev con `DEV_MODE=1` e `NEXT_PUBLIC_API_BASE`), comandi test (pytest + ruff backend, vitest + playwright + eslint frontend), nota PWA, credenziali default `user`/`password`. Link a `docs/PLAN.md` e `docs/DATABASE.md` per i dettagli
- [docs/PLAN.md](PLAN.md): spuntato l'ultimo item della Definition of Done

**Stato finale MVP:**
- Tutte le 10 parti del piano completate, Definition of Done al 100% (salvo verifiche live opzionali che richiedono credito OpenRouter)
- PWA installabile aggiunta out-of-plan
- 31 test backend (1 skip live) + 19 vitest + playwright auth/kanban/ai-chat (live skip senza chiave)

---

## 2026-05-17 — PWA: app installabile (out-of-plan)

**Commit:** (vedi `git log`)

**Contesto:** verifica live MVP nel container Docker andata bene. L'utente ha chiesto di trasformarla in "app" e ha scelto la via PWA (installabile via browser, niente Electron/Tauri).

**Fatto:**
- [frontend/public/icon.svg](../frontend/public/icon.svg): icona principale 512x512 (sfondo navy + 4 colonne stilizzate brand)
- [frontend/public/icon-maskable.svg](../frontend/public/icon-maskable.svg): variante con safe-area centrata per Android adaptive icons
- [frontend/public/manifest.webmanifest](../frontend/public/manifest.webmanifest): metadati PWA (`name`, `short_name`, `start_url=/`, `scope=/`, `display=standalone`, `theme_color=#032147`, `background_color=#f7f8fb`, icone)
- [frontend/src/app/layout.tsx](../frontend/src/app/layout.tsx): aggiunti `metadata.manifest`, `metadata.appleWebApp`, `metadata.icons`, e `viewport.themeColor` (separati come da Next.js 14+ guideline)
- Build: `npm run build` ok, HTML root contiene `<link rel="manifest">`, `<meta name="theme-color">`, `<meta name="mobile-web-app-capable">`, `<link rel="apple-touch-icon">`
- Container Docker ricostruito (`scripts/stop.ps1 + start.ps1`): `/manifest.webmanifest` e `/icon.svg` rispondono 200
- [frontend/AGENTS.md](../frontend/AGENTS.md): nuova sezione PWA

**Decisione:**
- **No PNG** per le icone: SVG con `sizes: "any"` e supporto Chrome/Edge/Safari moderni (dal 2021). Evita l'installazione di Pillow nel venv backend per generare PNG one-shot
- **No service worker**: Chrome dal v117 non lo richiede piu' per il prompt di install. L'app non funziona offline ma "diventa app" (finestra dedicata, icona, no barra browser). Service worker sara' aggiunto se serve offline reale
- **Niente next-pwa o altre lib**: setup minimo con metadata API nativa di Next.js + asset statici. Zero dipendenze in piu'

**In sospeso:**
- Verifica manuale install nel browser: aprire http://localhost:8000 in Chrome -> icona "+" nella barra URL -> Install -> verifica che l'app si apra come finestra standalone
- Eventuale service worker per offline support (work item futuro)

---

## 2026-05-17 — Part 10: Sidebar AI chat nel frontend (MVP completato)

**Commit:** (vedi `git log`)

**Fatto:**
- [frontend/src/lib/api.ts](../frontend/src/lib/api.ts): aggiunti `ChatMessage`, `ChatAIResponse`, `chatAI(message, history)`. Mappa 502 a un messaggio user-friendly
- [frontend/src/components/AIChatSidebar.tsx](../frontend/src/components/AIChatSidebar.tsx): sidebar fissa a destra, controllata da prop `open`. Tre tipi di messaggio (user / assistant / system). State locale per `messages`, `input`, `loading`, `error`. Auto-scroll, auto-focus. Su `board_updated: true` chiama `onBoardUpdated()`; su `validation_error` mostra badge informativo; su `ApiError` banner `role="alert"`. La history mandata al backend è filtrata a soli `user`/`assistant` (i system message locali non escono)
- [frontend/src/components/KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx): nuova prop `reloadSignal?: number` (dipendenza dell'useEffect che chiama `getBoard()`) + prop `onOpenChat` per il button "Chat" nell'header
- [frontend/src/app/page.tsx](../frontend/src/app/page.tsx): orchestrazione di `chatOpen` e `boardReloadSignal`, renderizza sia `<KanbanBoard>` che `<AIChatSidebar>`
- [frontend/src/components/AIChatSidebar.test.tsx](../frontend/src/components/AIChatSidebar.test.tsx): 8 test Vitest (mock `chatAI`); copre render condizionale, empty state, append messaggi, `board_updated` -> callback, `validation_error` no-callback, error banner, history del secondo turno, `onClose`
- [frontend/tests/ai-chat.spec.ts](../frontend/tests/ai-chat.spec.ts): Playwright. Open/close della sidebar non richiede chiave AI; il test "live" `adds a card via the AI` è skippato senza `OPENROUTER_API_KEY`
- Vitest 19/19, ESLint clean, `next build` ok (3 route invariate: /, /login, /_not-found)

**Decisione di design (deviazione dal PLAN):**
- Il PLAN Part 10 indicava "**Decisione**: Context, più pulito visto che cresce un secondo consumer". Ho deviato e uso una semplice prop `reloadSignal: number` come bridge fra `AIChatSidebar` e `KanbanBoard`. Motivo: `KanbanBoard` ha logica complessa interna (optimistic update, rollback, debounce, refs); spostarla in Context era un refactor sproporzionato per un singolo consumer extra. La deviazione è documentata sia in PLAN.md che in [frontend/AGENTS.md](../frontend/AGENTS.md). Se in futuro la sidebar dovesse leggere/scrivere direttamente la board client-side (non solo triggerare un refresh), un `BoardContext` diventerebbe la scelta giusta

**In sospeso:**
- README di setup (dev mode + container mode) — unico item rimasto della Definition of Done complessiva
- Verifica live `ai-chat.spec.ts` con chiave OpenRouter reale (richiede credito)
- Verifica manuale end-to-end in container: `scripts/start.ps1`, login, aggiungere una card via chat, vedere lo state aggiornato dopo `docker restart pm-app`

---

## 2026-05-17 — Part 9: Chat AI con Structured Outputs

**Commit:** (vedi `git log`)

**Fatto:**
- [backend/app/ai_prompts.py](../backend/app/ai_prompts.py): `SYSTEM_PROMPT` che descrive shape di `BoardData`, vincoli (colonne immutabili tranne il `title`, no orphan/duplicate), e contratto di output `{reply, board_update: null | BoardData}`. `AI_RESPONSE_SCHEMA` (JSON Schema strict) + `RESPONSE_FORMAT` per OpenRouter. Helper `board_context_message(board_json)`
- [backend/app/ai.py](../backend/app/ai.py): `call_openrouter` esteso con `response_format` opzionale. Aggiunto endpoint `POST /api/ai/chat` con: build messaggi (system / board JSON / history filtrata `user`+`assistant` / user msg), chiamata structured, parsing JSON sicuro, riuso del validator `BoardData` di Part 6, controllo aggiuntivo "lista di column.id identica a quella in DB" (immutabile incluso ordine), persist via `board.data = proposed.model_dump_json()`
- Risposta `ChatResponse`: `{reply, board_updated, validation_error?}`. Errori upstream -> 502; parsing/validazione fallita -> `board_updated=false` con `validation_error` informativo (DB intatto)
- [backend/tests/conftest.py](../backend/tests/conftest.py): estratte le fixture `tmp_engine`/`client`/`auth_client` da `test_board.py` per riuso in `test_ai_chat.py`. `test_board.py` ripulito
- [backend/tests/test_ai_chat.py](../backend/tests/test_ai_chat.py): 8 test (auth, simple question, modify+persist, reject column-id change, reject orphan, invalid JSON, provider 502, message shape + response_format)
- Pytest totale: 31 passed, 1 skipped (live ping). Ruff clean

**Decisioni applicative:**
- `AI_RESPONSE_SCHEMA` permissivo lato JSON Schema (solo shape), la validazione semantica (no orphan/duplicate/unreferenced) resta in `BoardData` Pydantic + check "stesso elenco di column.id". Cosi' i messaggi d'errore restano puntuali e non duplichiamo la logica
- Lista di `column.id` confrontata in ordine (non come set): assicuro che neppure il riordino delle colonne sia possibile via chat AI
- History filtrata server-side: solo ruoli `user`/`assistant` (no system injection dal client)

**In sospeso:**
- Verifica live `/api/ai/chat` con chiave OpenRouter reale (deve restituire structured output valido dal modello `openai/gpt-oss-120b`)
- Part 10: sidebar chat AI nel frontend

---

## 2026-05-17 — Part 8: Connettività AI base (OpenRouter)

**Commit:** (vedi `git log`)

**Fatto:**
- [backend/app/ai.py](../backend/app/ai.py): `async call_openrouter(messages)` verso `https://openrouter.ai/api/v1/chat/completions`, modello `openai/gpt-oss-120b`, timeout 30s. Ritorna `{content, prompt_tokens, completion_tokens}`. Log info con i token counts; mai logga la chiave. Errori upstream (timeout, transport, 4xx/5xx, payload malformato) vengono catturati e ri-sollevati come `AIError` con messaggio generico
- [backend/app/ai.py](../backend/app/ai.py) include anche `router` con `POST /api/ai/ping` (protetto da `require_auth`): chiama l'AI con "What is 2+2? Reply with just the number." e mappa `AIError` -> HTTP 502
- [backend/app/main.py](../backend/app/main.py): include `ai_router`
- [backend/tests/test_ai.py](../backend/tests/test_ai.py): 8 test (1 skip live). Mock di `call_openrouter` per i test del router; `httpx.MockTransport` per il client OpenRouter (token logging, timeout, 429). Verifica esplicita che la chiave non finisca mai in log/eccezioni
- Pytest totale: 23 passed, 1 skipped (live). Ruff clean

**Decisioni applicative:**
- Modulo singolo `ai.py` per client + router (no over-engineering: il router ha una sola route e dipende direttamente dal client). Se Part 9 cresce, splitto in `ai_client.py` + `ai_routes.py`
- `AIError` come exception applicativa interna; il router la traduce in `HTTPException(502)`. Il client esterno vede solo messaggi generici (`"AI provider timed out"`, `"AI provider returned an error"`, ecc.)
- Live test marcato `@pytest.mark.skipif` su env var: zero costo in CI/dev locale senza chiave

**In sospeso:**
- Test live `test_ai_ping_returns_4_live` con `OPENROUTER_API_KEY` reale (richiede credito su OpenRouter)
- Part 9: structured outputs + endpoint `/api/ai/chat` con contesto board

---

## 2026-05-16 — Verifica manuale persistenza DB cross-restart

**Eseguita su Docker Desktop / Windows 11. Risultato: tutto ok.**

Procedura:
- `scripts/start.ps1` -> healthy
- Login -> board vuota (DB seed) -> aggiunta card "Pewrsist Test / Vediamo se funziona" in Backlog
- `docker restart pm-app` -> attesa healthy -> reload browser -> la card e' ancora presente
- `scripts/stop.ps1`

Conferma che:
- Il volume `./data:/app/data` funziona end-to-end
- Il PUT /api/board del frontend (Part 7) scrive davvero su disco
- Il lifespan startup di main.py riapre il DB esistente senza re-seedare
- Il seed e' idempotente (esiste gia' user `user` -> non riapplica)

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
