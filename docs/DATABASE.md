# Database (SQLite)

Schema e decisioni di modellazione per la persistenza del progetto. Lo schema è volutamente minimale: il MVP ha un solo utente seed (`user`), una sola board per utente, e nessuno storico chat AI sul server.

Per il flusso di lettura/scrittura via API vedi [PLAN.md Part 6](PLAN.md#part-6-backend-api-per-il-kanban).

---

## File del DB e persistenza

- File: `data/kanban.db` (path relativo alla root del progetto)
- In container: la directory `/app/data/` è montata dal volume host `./data/` (vedi [scripts/start.sh](../scripts/start.sh) / `.ps1`)
- Path configurabile via env var `DB_PATH` (default `data/kanban.db`)
- WAL mode raccomandato per riaprire il DB in lettura concorrente (`PRAGMA journal_mode=WAL`) — impostato all'avvio dell'app
- Niente sistema di migration nell'MVP: `CREATE TABLE IF NOT EXISTS` allo startup. Se in futuro lo schema cambia, valutiamo Alembic.

---

## DDL completo

```sql
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boards (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL UNIQUE,
    data       TEXT    NOT NULL CHECK (json_valid(data)),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

Note:
- `boards.user_id` è `UNIQUE`: nell'MVP **un utente ha al massimo una board**. Se in futuro vorremo multi-board per user, basta togliere il vincolo e introdurre `name`/`order`.
- `boards.data` è il JSON serializzato della struttura `BoardData` (vedi sotto). `CHECK (json_valid(data))` blocca a livello DB qualunque JSON malformato in scrittura.
- `ON DELETE CASCADE` su `user_id`: cancellare un user cancella la sua board. Difensivo — nell'MVP non cancelliamo mai user.
- `created_at` / `updated_at`: timestamp UTC. L'app aggiorna esplicitamente `updated_at` ad ogni PUT.

---

## Razionale: JSON in colonna vs tabelle normalizzate

**Decisione: JSON in colonna.** Motivi:

1. **Shape allineata al frontend.** `BoardData` esiste già nel frontend ([frontend/src/lib/kanban.ts](../frontend/src/lib/kanban.ts)). Conservare la stessa shape lato server elimina mapping e divergenze.
2. **Niente query parziali.** L'MVP fa solo "leggi tutta la board" / "salva tutta la board". Nessun caso d'uso richiede query tipo "tutte le card in colonna X" lato SQL.
3. **Operazioni atomiche.** Un drag-drop sposta una card tra colonne: con tabelle normalizzate sarebbero almeno due UPDATE; con JSON è un singolo replace della colonna `data`. Niente transazioni da gestire a mano.
4. **Validazione robusta.** Il `CHECK (json_valid(data))` blocca JSON malformato; la validazione semantica (cardId orfani, duplicati) è in Pydantic prima della scrittura (Part 6).
5. **Reversibilità.** Se in futuro serve normalizzare (per query analytics, per esempio), la migrazione è leggibile: parsiamo il JSON e popoliamo `columns` + `cards` tables.

Trade-off accettato: niente query SQL su contenuti delle card. Per l'MVP non serve.

---

## Shape del JSON in `boards.data`

Identica a `BoardData` del frontend:

```ts
type Card = { id: string; title: string; details: string };
type Column = { id: string; title: string; cardIds: string[] };
type BoardData = {
  columns: Column[];                  // ordine significativo
  cards: Record<string, Card>;        // mappa cardId -> Card
};
```

Vincoli **semantici** validati lato app (Pydantic) prima della scrittura:
- Ogni `cardId` referenziato in `columns[*].cardIds` esiste in `cards`
- Ogni chiave di `cards` è uguale al `cards[k].id`
- Nessun `cardId` duplicato (né dentro la stessa colonna, né fra colonne diverse)
- Nessun `cardId` orfano in `cards` (presente in `cards` ma non in nessuna colonna)
- Numero e set di `column.id` immutabili fra una PUT e l'altra (modifica permessa: `column.title`; aggiunta/rimozione colonne **non** permessa nell'MVP)

---

## Empty state seed (default per il primo login)

All'avvio dell'app: se non esiste utente `user`, lo crea e crea la sua board con **5 colonne vuote** (allineate alle column ID del frontend):

```json
{
  "columns": [
    { "id": "col-backlog",   "title": "Backlog",     "cardIds": [] },
    { "id": "col-discovery", "title": "Discovery",   "cardIds": [] },
    { "id": "col-progress",  "title": "In Progress", "cardIds": [] },
    { "id": "col-review",    "title": "Review",      "cardIds": [] },
    { "id": "col-done",      "title": "Done",        "cardIds": [] }
  ],
  "cards": {}
}
```

Differenza rispetto a `initialData` del frontend: qui **niente card demo**, board pulita. Le card demo del frontend [src/lib/kanban.ts](../frontend/src/lib/kanban.ts) servivano per testare la UI quando lo state era in-memory; con la persistenza, la "verità" sta nel DB e il primo login mostra una board vuota.

---

## Esempio di `boards.data` dopo qualche modifica

```json
{
  "columns": [
    { "id": "col-backlog",   "title": "Idee",        "cardIds": ["card-abc123"] },
    { "id": "col-discovery", "title": "Discovery",   "cardIds": [] },
    { "id": "col-progress",  "title": "In Progress", "cardIds": ["card-def456"] },
    { "id": "col-review",    "title": "Review",      "cardIds": [] },
    { "id": "col-done",      "title": "Done",        "cardIds": [] }
  ],
  "cards": {
    "card-abc123": {
      "id": "card-abc123",
      "title": "Sondaggio onboarding",
      "details": "Domande aperte + NPS sui primi 14 giorni."
    },
    "card-def456": {
      "id": "card-def456",
      "title": "Prototipo grafico card",
      "details": "Provare densità verticale e icone di stato."
    }
  }
}
```

Nota: `col-backlog` è stata rinominata da "Backlog" → "Idee" (operazione permessa). Le 5 colonne sono ancora le stesse, nello stesso ordine, con gli stessi `id`.

---

## Storico chat AI

**Decisione MVP: nessuna tabella `messages`.**

Lo storico della conversazione AI è gestito **lato client**: il frontend tiene la history in state locale del componente `AIChatSidebar` (Part 10) e la rispedisce intera ad ogni request a `POST /api/ai/chat` (Part 9).

Conseguenze:
- Reload della pagina = chat history persa (atteso per l'MVP)
- Zero schema/migration extra sul DB
- Il backend resta stateless rispetto alla chat (eccetto la session cookie per l'auth)

Se in futuro vorremo persistere la chat, basta aggiungere una tabella `messages (id, user_id, role, content, created_at)` senza toccare il resto.

---

## Cosa implementa Part 6

Riferimento operativo (vedi [PLAN.md Part 6](PLAN.md#part-6-backend-api-per-il-kanban)):
- `backend/app/db.py`: engine SQLite, `init_db()`, `seed_default_user()`
- `backend/app/models.py`: SQLAlchemy `User`, `Board`
- `backend/app/schemas.py`: Pydantic `Card`, `Column`, `BoardData` + validator semantici
- Endpoints `GET /api/board`, `PUT /api/board` protetti da `require_auth`
- Tests: persistenza cross-restart, validator orphan/duplicate cardId, seed iniziale
