# Frontend — Kanban Studio

Next.js client del Kanban board. **Stato attuale (Part 10 completata)**: login, board persistente con drag/drop e optimistic update, sidebar di chat AI che può consultare/modificare la board tramite `POST /api/ai/chat`. Vedi [../docs/PLAN.md](../docs/PLAN.md).

**Build mode (Part 3)**: `output: "export"` configurato in [next.config.ts](next.config.ts) per generare un sito statico (`frontend/out/`) servito da FastAPI alla root `/`. I font Google sono scaricati a build-time e serviti come asset statici sotto `_next/static/media/` (nessuna dipendenza da Google Fonts a runtime).

## Stack

- Next.js 16.1.6 (App Router) — vedi [next.config.ts](next.config.ts)
- React 19.2.3 + TypeScript 5
- Tailwind CSS 4 (via `@tailwindcss/postcss`) — vedi [src/app/globals.css](src/app/globals.css)
- @dnd-kit (`core`, `sortable`, `utilities`) per drag and drop
- `clsx` per la composizione di className condizionali
- Font Google: `Space_Grotesk` (display) e `Manrope` (body) caricati in [src/app/layout.tsx](src/app/layout.tsx)

## Testing

- **Unit/Integration**: Vitest + Testing Library (`@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`) — config in [vitest.config.ts](vitest.config.ts)
  - Ambiente `jsdom`, alias `@` → `src/`
  - Setup file: [src/test/setup.ts](src/test/setup.ts)
  - Include: `src/**/*.{test,spec}.{ts,tsx}`
- **E2E**: Playwright (solo Chromium) — config in [playwright.config.ts](playwright.config.ts)
  - `baseURL: http://127.0.0.1:3000`, avvia automaticamente `npm run dev`
  - Test in [tests/](tests/)

### Script npm
- `npm run dev` — dev server Next.js
- `npm run build` — build production
- `npm run start` — serve il build production
- `npm run lint` — ESLint (config Next.js, [eslint.config.mjs](eslint.config.mjs))
- `npm run test:unit` — Vitest (run once)
- `npm run test:unit:watch` — Vitest in watch
- `npm run test:e2e` — Playwright
- `npm run test:all` — unit + E2E

## Struttura

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # RootLayout con font e metadata
│   │   ├── page.tsx          # Home: auth-gate + <KanbanBoard /> + <AIChatSidebar /> orchestration
│   │   ├── login/
│   │   │   ├── page.tsx      # Login form (Part 4)
│   │   │   └── page.test.tsx # Vitest del form
│   │   ├── globals.css       # Tailwind + variabili CSS palette
│   │   └── favicon.ico
│   ├── components/
│   │   ├── KanbanBoard.tsx          # Root del board, owner dello state
│   │   ├── KanbanBoard.test.tsx     # Test Vitest del board
│   │   ├── KanbanColumn.tsx         # Singola colonna (droppable)
│   │   ├── KanbanCard.tsx           # Singola card (sortable)
│   │   ├── KanbanCardPreview.tsx    # Render in DragOverlay
│   │   ├── NewCardForm.tsx          # Form inline per aggiungere card
│   │   ├── AIChatSidebar.tsx        # Sidebar di chat AI (Part 10)
│   │   └── AIChatSidebar.test.tsx   # Test Vitest della sidebar
│   ├── lib/
│   │   ├── kanban.ts                # Tipi, dati iniziali, logica moveCard, createId
│   │   ├── kanban.test.ts           # Test Vitest della logica moveCard
│   │   └── api.ts                   # apiFetch + login/logout/getMe/getBoard/updateBoard/chatAI (Part 4 + 7 + 10); base URL via NEXT_PUBLIC_API_BASE
│   └── test/setup.ts                # Setup Vitest (carica jest-dom)
├── tests/
│   ├── kanban.spec.ts               # Playwright E2E (load, add card + reload persistence) — fa login in beforeEach
│   ├── auth.spec.ts                 # Playwright E2E del flusso auth (Part 4)
│   ├── ai-chat.spec.ts              # Playwright E2E della sidebar AI (test "live" skip se no OPENROUTER_API_KEY) (Part 10)
│   └── helpers.ts                   # loginAsTestUser per i test E2E
├── public/                          # Asset statici Next.js
├── next.config.ts
├── playwright.config.ts
├── vitest.config.ts
├── tsconfig.json
├── eslint.config.mjs
├── postcss.config.mjs
└── package.json
```

## Modello dati

Definito in [src/lib/kanban.ts](src/lib/kanban.ts) e identico alla shape Pydantic backend ([backend/app/schemas.py](../backend/app/schemas.py)):

```ts
type Card   = { id: string; title: string; details: string };
type Column = { id: string; title: string; cardIds: string[] };
type BoardData = {
  columns: Column[];                 // ordine delle colonne
  cards: Record<string, Card>;       // mappa cardId → Card
};
```

- I `cardIds` nelle colonne sono **riferimenti** alle card in `cards`. Le card sono memorizzate in una mappa per lookup O(1) e per evitare duplicazione.
- `initialData` (5 colonne demo + card di esempio) **non e' piu' usato in produzione** dopo Part 7 (la board reale viene dal backend, seedata vuota). Resta in `kanban.ts` come riferimento e per fixtures di test.
- `moveCard(columns, activeId, overId)` gestisce sia il riordino dentro la stessa colonna sia lo spostamento tra colonne; accetta sia un `cardId` sia un `columnId` come `overId` (drop su area vuota → append in coda).
- `createId(prefix)` genera ID univoci combinando random base36 + timestamp.

## Componenti

### `KanbanBoard` ([src/components/KanbanBoard.tsx](src/components/KanbanBoard.tsx))
- Component client (`"use client"`), owner dello state (`useState<BoardData | null>`). Carica via `getBoard()` al mount; mostra "Loading board..." finche' la risposta arriva (Part 7)
- Configura `DndContext` di @dnd-kit con `PointerSensor` (attivazione a 6px) e `closestCorners`
- Gestisce `DragOverlay` per il feedback visivo durante il drag (renderizza `KanbanCardPreview`)
- Handler: `handleDragStart`, `handleDragEnd`, `handleRenameColumn` (debounced 500ms), `handleAddCard`, `handleDeleteCard`
- **Optimistic update + rollback**: ogni mutazione applica il next state subito e chiama `updateBoard(next)`. Su errore, fa rollback a `lastSavedRef.current` (ultimo state confermato dal server) e mostra banner `role="alert"`
- **Debounce rename**: state immediato + `setTimeout(persist, 500ms)`, cosi' un keystroke per ogni lettera = una sola PUT. Una mutazione non-rename (add/delete/drag) flusha il timer pendente per evitare race
- Layout: header con titolo "Kanban Studio" + griglia 5 colonne; banner `saveError` sotto l'header se l'ultima PUT e' fallita

### `KanbanColumn` ([src/components/KanbanColumn.tsx](src/components/KanbanColumn.tsx))
- `useDroppable({ id: column.id })` per accettare drop sulla colonna
- `SortableContext` con `verticalListSortingStrategy` per il riordino interno
- Titolo modificabile inline tramite `<input>` (chiama `onRename` ad ogni keystroke; il debounce vive in `KanbanBoard`)
- Mostra "Drop a card here" come empty state
- Include `NewCardForm` in fondo
- `data-testid="column-{id}"` per i test

### `KanbanCard` ([src/components/KanbanCard.tsx](src/components/KanbanCard.tsx))
- `useSortable({ id: card.id })` con transform/transition standard di @dnd-kit
- Spread di `{...attributes}` e `{...listeners}` su `<article>` per attivare drag handle su tutta la card
- Pulsante "Remove" con `aria-label="Delete {title}"`
- `data-testid="card-{id}"` per i test

### `KanbanCardPreview` ([src/components/KanbanCardPreview.tsx](src/components/KanbanCardPreview.tsx))
- Versione "statica" della card usata in `DragOverlay`. Stesso layout di `KanbanCard` ma senza handler e senza pulsante delete.

### `NewCardForm` ([src/components/NewCardForm.tsx](src/components/NewCardForm.tsx))
- Toggle: pulsante "Add a card" → mostra form (title + details + submit/cancel)
- Validazione minima: `title.trim()` obbligatorio
- Chiama `onAdd(title, details)` su submit, poi resetta lo state

### `AIChatSidebar` ([src/components/AIChatSidebar.tsx](src/components/AIChatSidebar.tsx))
- Sidebar fissa a destra (`fixed right-0 top-0 h-screen w-full max-w-sm`), renderizzata solo quando `open` è `true` (controllata dal parent in `app/page.tsx`)
- State locale: `messages`, `input`, `loading`, `error`. La history della chat è persa al refresh della pagina (decisione MVP)
- Tre tipi di messaggio renderizzati: `user` (bubble blu a destra), `assistant` (bubble grigia a sinistra), `system` (badge centrale, usato per "Board updated." o "Update rejected: ...")
- Su `Send`: append user message, chiama `chatAI(message, history)` con la sola conversazione `user`/`assistant` (i messaggi `system` non vanno al backend), append assistant reply. Se `board_updated`, chiama `onBoardUpdated()` -> il parent incrementa `reloadSignal` -> `KanbanBoard` rifa il fetch
- Su `validation_error`: messaggio `system` informativo, niente refresh
- Su `ApiError`: banner `role="alert"` sopra la form
- Auto-scroll alla fine della lista quando arrivano messaggi nuovi; input auto-focus quando la sidebar viene aperta

## Palette colori

Definita in [src/app/globals.css](src/app/globals.css) come variabili CSS — coerente con [../AGENTS.md](../AGENTS.md):

| Variabile | Hex | Uso |
|-----------|-----|-----|
| `--accent-yellow` | `#ecad0a` | accent lines, highlights |
| `--primary-blue` | `#209dd7` | link, sezioni chiave |
| `--secondary-purple` | `#753991` | submit button, azioni importanti |
| `--navy-dark` | `#032147` | titoli principali |
| `--gray-text` | `#888888` | testo di supporto, label |
| `--surface` | `#f7f8fb` | sfondo pagina |
| `--surface-strong` | `#ffffff` | sfondo card/colonna |
| `--stroke` | `rgba(3,33,71,0.08)` | bordi |
| `--shadow` | `0 18px 40px rgba(3,33,71,0.12)` | shadow elevati |

Font: `--font-display` (Space Grotesk, classe `.font-display`) per titoli; `--font-body` (Manrope, default body).

## Convenzioni

- Componenti `.tsx` in PascalCase con named export (`export const KanbanBoard = ...`); non default export
- Test colocati: `Foo.test.tsx` accanto a `Foo.tsx`
- Test E2E in `tests/` (esclusi dalla include di Vitest)
- Tipi condivisi in `src/lib/kanban.ts`
- Nessun state globale (Context, Redux, Zustand): la board vive in `useState` di `KanbanBoard`, la chat in `useState` di `AIChatSidebar`. Il bridge fra i due componenti è un semplice `reloadSignal: number` gestito da `app/page.tsx` — quando l'AI conferma `board_updated: true`, la sidebar chiama `onBoardUpdated()`, il parent incrementa il contatore, l'effect di `KanbanBoard` rifa il fetch (decisione MVP, deviazione minima dal Context previsto nel PLAN per non riscrivere KanbanBoard)
- Stile: Tailwind utility-first, variabili CSS per i colori del brand (mai colori hardcoded nei className)
- Niente emoji nel codice né nei commenti (vedi [../AGENTS.md](../AGENTS.md))

## Auth flow (Part 4)

- `src/app/page.tsx` (client) chiama `getMe()` al mount: se 401 → `router.replace("/login")`, altrimenti renderizza `<KanbanBoard onLogout={...} />`. Mostra "Loading..." durante la verifica.
- `src/app/login/page.tsx` invia username/password a `POST /api/auth/login`; mostra `<p role="alert">` con il messaggio dell'`ApiError` (401 → "Invalid username or password."). Su successo `router.replace("/")`.
- Logout: il button nell'header del Kanban chiama `logout()` (`POST /api/auth/logout`) e fa `router.replace("/login")`.
- Tutte le fetch usano `credentials: "include"` via `apiFetch` in [src/lib/api.ts](src/lib/api.ts).
- Per il flow dev (Next.js :3000 + FastAPI :8000), `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000` è impostato dal `playwright.config.ts` per i test E2E. Per sviluppo locale settarla in `frontend/.env.local`.

## Stato finale MVP

Tutte le 10 parti di [../docs/PLAN.md](../docs/PLAN.md) sono implementate. Per la verifica end-to-end (login -> board persistente -> chat AI) serve `OPENROUTER_API_KEY` reale; tutto il resto gira anche senza chiave.