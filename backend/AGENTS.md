# Backend

Backend FastAPI dell'app PM. **Stato attuale (Part 2 completata)**: scaffolding minimo con `/api/health` e mount degli statici. Auth, DB, AI verranno aggiunti nelle parti successive del piano (vedi [../docs/PLAN.md](../docs/PLAN.md)).

## Stack previsto

- Python 3.12
- FastAPI + Uvicorn (server ASGI)
- `uv` come package manager (gestione dipendenze e venv)
- SQLAlchemy (sync) su SQLite
- Pydantic per validazione I/O
- Starlette `SessionMiddleware` per la sessione cookie-based
- `httpx` per le chiamate a OpenRouter
- pytest + FastAPI `TestClient` per i test
- `ruff` come linter

## Struttura

```
backend/
├── pyproject.toml         # dipendenze + config ruff (Part 2 — presente)
├── uv.lock                # lockfile committato (Part 2 — presente)
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app + /api/health + mount static + CORS dev (Part 2 — presente)
│   ├── auth.py            # login/logout/me + require_auth dependency (Part 4)
│   ├── db.py              # engine SQLite, init_db, seed (Part 6)
│   ├── models.py          # SQLAlchemy models (Part 6)
│   ├── schemas.py         # Pydantic schemas (Part 6)
│   ├── ai.py              # client OpenRouter (Part 8)
│   └── ai_prompts.py      # system prompt + structured output schema (Part 9)
├── static/                # placeholder hello-world (Part 2); sostituito dal build Next.js (Part 3)
└── tests/
    ├── test_health.py     # Part 2 — presente
    ├── test_auth.py       # Part 4
    ├── test_board.py      # Part 6
    └── test_ai.py         # Part 8-9
```

## Configurazione runtime

Variabili d'ambiente lette dal backend (definite in `.env`, vedi `.env.example`):

| Variabile | Scopo | Parte |
|-----------|-------|-------|
| `OPENROUTER_API_KEY` | autenticazione a OpenRouter | 8 |
| `SESSION_SECRET` | firma del cookie di sessione | 4 |
| `DEV_MODE` | se `1`, abilita CORS verso `localhost:3000` | 2 |
| `DB_PATH` | path al file SQLite (default `data/kanban.db`) | 6 |

## Convenzioni

- Nessun emoji nel codice/log/commenti (vedi [../AGENTS.md](../AGENTS.md))
- Codice formattato e linted da `ruff` (line-length 100, target `py312`)
- Test isolati per file: fixture pytest `tmp_db` per il DB temporaneo (Part 6+)
- Tutti gli endpoint applicativi sotto il prefisso `/api/`; tutto il resto serve la SPA statica
- Risposte d'errore: `HTTPException` con messaggi generici, mai dettagli interni o chiavi

## Note di build

- Il `Dockerfile` (root) esegue `uv sync --frozen --no-dev` usando `backend/uv.lock`. Per aggiornare le dipendenze: modificare `pyproject.toml`, eseguire `uv sync` da `backend/`, committare `uv.lock`.
- Lo static mount avviene solo se `backend/static/` esiste, per non rompere i test quando si lavora senza i file statici.
