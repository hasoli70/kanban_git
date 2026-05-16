# Scripts

Script di avvio e stop del container Docker per Mac, Linux e Windows. **Stato attuale (Part 2 completata)**: tutti gli script sono presenti e funzionali.

## File

| Script | Piattaforma | Comportamento |
|--------|-------------|---------------|
| `start.sh` | Mac/Linux | `docker build` → `docker run` con volume + env-file → attende healthcheck `healthy` (timeout 120s) |
| `start.ps1` | Windows PowerShell | Stesso comportamento di `start.sh` con sintassi PowerShell |
| `stop.sh` | Mac/Linux | `docker stop pm-app && docker rm pm-app` (idempotente) |
| `stop.ps1` | Windows PowerShell | Stesso comportamento di `stop.sh` (idempotente) |

## Convenzioni

- Tutti gli script si aspettano di essere eseguiti dalla **root del progetto** (non da `scripts/`)
- Image tag fisso: `pm-app`
- Container name fisso: `pm-app`
- Porta esposta: `8000`
- Volume montato: `./data:/app/data` (per la persistenza di SQLite)
- Caricano l'env da `.env` nella root (`--env-file .env`)
- Lo `start` esce con codice 0 solo dopo che lo healthcheck Docker passa a `healthy`
- Lo `stop` è idempotente (non fallisce se il container non esiste)

## Uso (dev mode)

Per lo sviluppo quotidiano si lavora senza Docker (`uv run uvicorn ...` + `npm run dev`). Gli script in questa directory servono per la modalità container integrata. Vedi sezione "Workflow di sviluppo" in [../docs/PLAN.md](../docs/PLAN.md).
