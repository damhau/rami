# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Web-based, real-time, online multiplayer **Rami Portugais** (Portuguese Rummy) — the
11-contract rummy variant. `DESIGN.md` is the authoritative rules spec (sections are
referenced from code comments, e.g. §3.9); `docs/Rami_portugais_regles_v2.pdf` is the
original rulebook; `mockups/index.html` is the UI reference.

- **Backend:** FastAPI + WebSockets, Python 3.12+, `uv`. A pure rules engine drives an
  authoritative in-memory server.
- **Frontend:** React 19 + Vite + TypeScript + Tailwind v4 + shadcn/ui + Zustand.

## Commands

Backend (run from repo root):

```bash
uv sync                                   # create venv, install deps
uv run uvicorn rami.main:app --reload     # dev server on :8000
uv run ruff check .                       # lint
uv run ruff format --check .              # format check
uv run mypy src/                          # type-check (strict)
uv run pytest -x                          # tests
uv run pytest tests/test_engine.py -k free_card   # a single test / pattern
```

Frontend (run from `web/`):

```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api + /ws to :8000
npm run build      # tsc -b && vite build -> web/dist
npm run lint       # tsc -b --noEmit (type-check only; no ESLint)
```

Port overrides when 8000/5173 are taken:

```bash
uv run uvicorn rami.main:app --port 8100
VITE_PORT=5180 VITE_API_TARGET=localhost:8100 npm run dev
```

Docker builds the SPA and serves it from FastAPI on one port (same-origin, no proxy):
`docker build -t rami:latest . && docker run --rm -p 8000:8000 rami:latest`.

## Architecture

Requests flow **client → transport → session → engine**, and the engine is the only place
game rules live.

### Rules engine — `src/rami/game/` (pure, deterministic, no I/O)

The heart of the app. `engine.apply(state, intent) -> (new_state, events)` is the single
mutation entry point; **it deep-copies and never mutates the input**, so a rejected move
(raised `AppError`) leaves the caller's state untouched. Randomness comes *only* from
`state.rng_seed` + `shuffle_count` (see `_make_rng`), so any game is fully reproducible.

- `cards.py` — 110-card deck (two 52-card decks + 6 jokers), ranks 1–13 with Ace low/high
  in runs, point values.
- `melds.py` — set/run validation and joker logic. A meld stores only its physical cards;
  what each joker *represents* (`Meld.represents`) is **recomputed from contents** on every
  `refresh()`, never stored persistently — this keeps joker auto-reassignment and recovery
  honest.
- `contracts.py` — the 11 round contracts (`CONTRACTS`) and `satisfies_contract`, a greedy
  matcher (one laid meld per requirement, extras allowed).
- `intents.py` — the frozen intent records; `Intent` is their union. The only way to drive
  a started game.
- `state.py` — `GameState`, `PlayerState`, `Phase` enum, `Event`. Phases:
  `LOBBY → AWAIT_DRAW → AWAIT_DISCARD → … → ROUND_OVER → GAME_OVER`.
- `scoring.py` — end-of-round hand penalty (jokers = 25).
- `engine.py` — `apply`, `new_game`, `start_round`, `_end_round`. Enforces turn order,
  phase, the go-out rule (first lay must satisfy the contract **and** total ≥ 40 pts), the
  discard-pickup obligation (`taken_from_discard_id` must be laid before discarding), and
  the free-card ("carte gratuite") offer after a stock draw.
- `ai.py` — a pure heuristic computer player; `next_bot_intent(state, seat)` returns the
  bot's next move (draws stock, goes out when contract + 40 pts is reachable, lays off,
  discards its worst card). Used by the solo ("vs computer") mode.

**Free-card model (3+ players):** drawing from the stock refuses the visible discard and
opens a `FreeCardOffer` to the following seats *without blocking the drawer* — they proceed
to `AWAIT_DISCARD` immediately. Following seats may `ClaimFreeCard`/`PassFreeCard`
out-of-turn until the drawer discards, which clears the offer. There is no `FREE_CARD`
phase and no timeout. 2-player games get no free-card offer.

### Table lifecycle — `src/rami/tables/`

`TableManager` (one process-wide, in-memory registry) → `GameSession` per game. A session
owns the authoritative `GameState`, the `Seat` list (each seat has a secret `token`), and an
`asyncio.Lock` so intents apply one at a time. `router.py` exposes REST for the pre-game
flow (create/join/inspect) under `/api/v1/tables`; seat 0 is the host.

### Realtime — `src/rami/realtime/`

`ws.py` serves `/ws/table/{code}?token=…`. Per inbound message: parse (`protocol.py`
Pydantic discriminated union) → apply under `session.lock` → broadcast. **`protocol.py` also
does per-seat redaction**: `build_snapshot` gives each player their own hand but opponents
only as counts (`hand_count`) — never send raw `GameState` to a client. `connections.py`
tracks live sockets per (code, seat). After each broadcast (and on connect), `_run_bots`
drives any bot seats (`Seat.is_bot`) — applying `ai.next_bot_intent` moves with a short
delay — until it is a human's turn again. Solo games are created via `TableManager.create_solo`
(host + N bots, started immediately) behind `POST /api/v1/tables/solo`.

### Core — `src/rami/core/`

`config.py` (`RAMI_`-prefixed env settings, cached `get_settings`), `logging.py` (JSON logs +
request middleware), `exceptions.py`. Domain errors subclass `AppError` with a `.code` /
`.message`; the transport turns them into `error` messages and the engine raises them to
reject moves — prefer these over bare exceptions.

### Frontend — `web/src/`

`store.ts` is the Zustand store and owns the single WebSocket: it holds `snapshot`, derives a
human-readable event `log`, and manages card `selected` / `tray` (staged melds) state.
`types.ts` mirrors the server protocol — **keep it in sync with `protocol.py`** when
changing wire shapes. Components: `App` → `Home`/`Lobby`/`GameTable`/`Table`, plus
`PlayingCard`, `Scoreboard`, `Dialogs`, and shadcn `ui/`. `lib/api.ts` calls the REST
endpoints.

## Conventions & gotchas

- **Single process only.** All game state is in memory; do not scale to multiple
  workers/replicas (each would hold divergent state). This is intentional.
- **Keep the engine pure.** No I/O, no clock, no global RNG inside `game/` — thread seeds
  through state. This is what makes `tests/` (`conftest.py` builds states directly) fast and
  deterministic.
- mypy runs in **strict** mode on `src/` with the pydantic plugin; ruff line-length is 100
  (E501 is left to the formatter).
- The client hand and staged tray are reconciled against every snapshot (cards no longer in
  hand are dropped) — server state is always the source of truth.

## Releases & commits

- **Use Conventional Commits** for every commit (`feat:`, `fix:`, `chore:`, `docs:`,
  `refactor:`, `test:`, …). Commitizen derives the next version from them.
- **Cut a release with `uv run cz bump`** — it bumps the version in `pyproject.toml`
  (`[tool.commitizen]`), updates `CHANGELOG.md`, commits with `[skip ci]`, and creates a
  `v$version` tag (`tag_format = "v$major.$minor.$patch$prerelease"`). Push with
  `git push --follow-tags`.
- **The `v*` tag is what ships.** Pushing it triggers `.github/workflows/docker-publish.yml`,
  which builds/pushes `damienh/rami:<version>` and updates the image tag in the
  `damhau/k8s-argocd` gitops repo for ArgoCD. `type=semver` strips the leading `v`, so tag
  `v0.1.3` → image `0.1.3`. Do not hand-edit the version or create `v*` tags by other means.
