# Rami Portugais

Web-based, real-time, online multiplayer **Rami Portugais** (Portuguese Rummy) —
the 11-contract rummy variant. See [`DESIGN.md`](./DESIGN.md) for the full design
and the implemented rules, and [`mockups/index.html`](./mockups/index.html) for the
UI reference.

- **Backend:** FastAPI + WebSockets, Python 3.12+, `uv`. A pure, fully-tested
  rules engine drives an authoritative server.
- **Frontend:** React + Vite + TypeScript + Tailwind + shadcn/ui.

## Docker (one container: backend + built frontend)

The image builds the React app and serves it from FastAPI, so everything runs
same-origin on a single port — no proxy, no separate frontend server.

```bash
docker build -t rami:latest .
docker run --rm -p 8000:8000 rami:latest
# open http://localhost:8000
```

Single process only: game state lives in memory, so don't scale to multiple
workers/replicas (each would hold its own divergent state).

## Local development

Two terminals — the Vite dev server gives hot reload and proxies to the backend.

## Backend

```bash
uv sync                      # create the venv and install deps
uv run uvicorn rami.main:app --reload   # serve on http://localhost:8000
```

Quality gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -x
```

## Frontend

```bash
cd web
npm install
npm run dev                  # Vite dev server on http://localhost:5173
```

The dev server proxies `/api` and `/ws` to the backend on port 8000. Open the
printed URL, create a table, share the code, and a second browser/tab can join.

### Port overrides

If 8000 / 5173 are already taken, run the backend on another port and point the
dev server at it:

```bash
uv run uvicorn rami.main:app --port 8100
VITE_PORT=5180 VITE_API_TARGET=localhost:8100 npm run dev
```

## How to play (quick)

1. **Draw** from the stock or take the face-up discard (taking it obliges you to
   meld it — a go-out if you haven't gone out yet).
2. **Build a meld**: click hand cards to select them, then *Add as run* / *Add as
   set* to stage them; *Go out* / *Lay down* commits. Your first go-out must
   satisfy the round contract and total ≥ 40 points.
3. **After going out**, click a table meld with one card selected to lay off, or
   *↩ joker* to recover a joker by laying the exact card it represents.
4. **Discard** one card to end your turn. Shed all your cards to win the round;
   lowest total after 11 rounds wins the game.

## Layout

```
src/rami/
├── game/        # pure rules engine (cards, melds, contracts, state, engine, scoring)
├── tables/      # table lifecycle (create/join), in-memory manager
├── realtime/    # WebSocket protocol, connection manager, per-seat redaction
├── core/        # config, logging, exceptions
└── api/v1.py    # REST router aggregation
web/             # React client
tests/           # engine + transport tests
```
