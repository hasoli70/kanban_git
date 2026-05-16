# Frontend — Kanban Studio

Demo Next.js del Kanban board. Stato attuale: pura UI con state in-memory, nessuna integrazione backend, nessun login, nessuna chat AI. Verrà progressivamente integrato seguendo le parti definite in [../docs/PLAN.md](../docs/PLAN.md).

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
│   │   ├── page.tsx          # Home: renderizza <KanbanBoard />
│   │   ├── globals.css       # Tailwind + variabili CSS palette
│   │   └── favicon.ico
│   ├── components/
│   │   ├── KanbanBoard.tsx          # Root del board, owner dello state
│   │   ├── KanbanBoard.test.tsx     # Test Vitest del board
│   │   ├── KanbanColumn.tsx         # Singola colonna (droppable)
│   │   ├── KanbanCard.tsx           # Singola card (sortable)
│   │   ├── KanbanCardPreview.tsx    # Render in DragOverlay
│   │   └── NewCardForm.tsx          # Form inline per aggiungere card
│   ├── lib/
│   │   ├── kanban.ts                # Tipi, dati iniziali, logica moveCard, createId
│   │   └── kanban.test.ts           # Test Vitest della logica moveCard
│   └── test/setup.ts                # Setup Vitest (carica jest-dom)
├── tests/kanban.spec.ts             # Playwright E2E (load, add card, drag)
├── public/                          # Asset statici Next.js
├── next.config.ts
├── playwright.config.ts
├── vitest.config.ts
├── tsconfig.json
├── eslint.config.mjs
├── postcss.config.mjs
└── package.json
```

## Modello dati (in-memory)

Definito in [src/lib/kanban.ts](src/lib/kanban.ts):

```ts
type Card   = { id: string; title: string; details: string };
type Column = { id: string; title: string; cardIds: string[] };
type BoardData = {
  columns: Column[];                 // ordine delle colonne
  cards: Record<string, Card>;       // mappa cardId → Card
};
```

- I `cardIds` nelle colonne sono **riferimenti** alle card in `cards`. Le card sono memorizzate in una mappa per lookup O(1) e per evitare duplicazione.
- `initialData` contiene 5 colonne demo (Backlog, Discovery, In Progress, Review, Done) con card di esempio.
- `moveCard(columns, activeId, overId)` gestisce sia il riordino dentro la stessa colonna sia lo spostamento tra colonne; accetta sia un `cardId` sia un `columnId` come `overId` (drop su area vuota → append in coda).
- `createId(prefix)` genera ID univoci combinando random base36 + timestamp.

## Componenti

### `KanbanBoard` ([src/components/KanbanBoard.tsx](src/components/KanbanBoard.tsx))
- Component client (`"use client"`), unico owner dello state del board (`useState<BoardData>(initialData)`)
- Configura `DndContext` di @dnd-kit con `PointerSensor` (attivazione a 6px di distanza) e `closestCorners`
- Gestisce `DragOverlay` per il feedback visivo durante il drag (renderizza `KanbanCardPreview`)
- Handler: `handleDragStart`, `handleDragEnd`, `handleRenameColumn`, `handleAddCard`, `handleDeleteCard`
- Layout: header con titolo "Kanban Studio" + griglia 5 colonne (`lg:grid-cols-5`)

### `KanbanColumn` ([src/components/KanbanColumn.tsx](src/components/KanbanColumn.tsx))
- `useDroppable({ id: column.id })` per accettare drop sulla colonna
- `SortableContext` con `verticalListSortingStrategy` per il riordino interno
- Titolo modificabile inline tramite `<input>` (chiama `onRename` ad ogni keystroke — sarà da debounceare quando il backend salverà su ogni cambio, vedi PLAN Part 7)
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
- Nessun state globale ancora (Context, Redux, Zustand): tutto in `useState` del componente root `KanbanBoard`
- Stile: Tailwind utility-first, variabili CSS per i colori del brand (mai colori hardcoded nei className)
- Niente emoji nel codice né nei commenti (vedi [../AGENTS.md](../AGENTS.md))

## Cosa manca (rispetto al PLAN)

In ordine di esecuzione (vedi [../docs/PLAN.md](../docs/PLAN.md)):

1. Build statico (`output: "export"`) per essere servito da FastAPI (Part 3)
2. Pagina di login + redirect se non autenticato (Part 4)
3. Client API (`src/lib/api.ts`) che parla col backend invece dello state in-memory (Part 7)
4. Sidebar di chat AI (Part 10)
