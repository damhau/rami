# Rami Portugais — Design Document

> Web-based, real-time, online multiplayer implementation of **Rami portugais**
> (Portuguese Rummy), the 11-contract variant described in
> `docs/Rami_portugais_regles_v2.pdf`.

**Status:** Draft v0.2 — design & UI mockup phase; core rules ambiguities resolved.
**Last updated:** 2026-06-07

---

## 1. Vision

A browser game where 2–4 people play a full 11-round game of Rami portugais
together in real time. No install, no account: create a table, share a room
code, play. An authoritative Python server owns all game logic and state; the
browser is a thin, reactive view that sends *intents* ("draw from stock",
"meld these cards", "discard this card") and renders the state the server
broadcasts back.

### Design principles

1. **Server-authoritative.** The client never decides what is legal. It can
   *hint* (grey out illegal actions for UX), but the server re-validates every
   intent. This prevents cheating and keeps the rules in exactly one place.
2. **Pure, testable game engine.** The rules live in a side-effect-free Python
   module (no I/O, no sockets, no time). Everything about Rami portugais can be
   unit-tested by feeding states and intents and asserting on the next state.
3. **Thin transport.** WebSockets carry small JSON messages. The server is the
   single source of truth and pushes authoritative state to each seat (with
   per-seat redaction so you never see opponents' hands).
4. **Incremental.** v1 is human-only with in-memory tables. Persistence,
   accounts, bots, and reconnection-hardening are designed-for but deferred.

---

## 2. Decisions locked for v1

| Area | Decision |
|---|---|
| Backend | **FastAPI + WebSockets**, Python 3.12+, **uv**, domain-first layout |
| Frontend | **React (latest) + Vite + TypeScript + Tailwind + shadcn/ui** |
| Players | **Human-only** multiplayer (no AI bots in v1) |
| Identity | **Anonymous** — pick a display name, no signup |
| Tables | **Room-code** based (e.g. `RAMI-7F3K`), in-memory |
| Ace in runs | **Low and high, no wrap** — `A-2-3` ✅, `Q-K-A` ✅, `K-A-2` ❌ |
| Deck | **110 cards** = two 52-card decks **+ 6 jokers** |
| Joker (laid) | Counts as the **value of the card it represents** toward the 40-pt threshold |
| Free card | Claimable **only at the moment of refusal**, no discard cost, **max once per turn** |
| State storage | **In-memory** per process (single server instance in v1) |

---

## 3. Rules as implemented

This is the engine's interpretation of the PDF. Anything genuinely ambiguous is
collected in **§4 Open rules questions**; defaults chosen there are marked
`[default]`.

### 3.1 Material

- **110 cards:** two full 52-card French decks (104 cards) **+ 6 jokers**.
- The PDF's "108 cards" figure is a typo: **6 jokers is confirmed**, and keeping
  both decks intact gives 104 + 6 = 110. Deck composition is still a single
  config constant, so the exact count remains a one-line change if ever needed.

### 3.2 Cards & values

| Card | In-run rank | Point value |
|---|---|---|
| Ace (A) | 1 (low) **and** 14 (high), no wrap | **11** |
| King (K) | 13 | 10 |
| Queen (Q) | 12 | 10 |
| Jack (J) | 11 | 10 |
| 10 … 2 | face | face value (10 … 2) |
| Joker | represents any card | **25** in hand · see note |

Suits: ♠ spades, ♥ hearts, ♦ diamonds, ♣ clubs.

> **Joker value is context-dependent.** A joker **left in your hand** at the end
> of a round costs a flat **25**. A joker **laid in a meld** is worth the **point
> value of the card it currently represents** — e.g. a joker standing in for a 9
> counts as **9** toward the 40-point going-out threshold, a joker for a King
> counts as **10**. (It still represents that exact card per the joker rules in
> §3.9.)

### 3.3 Players & setup

- 2–4 players (engine allows more; lobby caps at 4 for v1).
- Each player is dealt **13 cards**.
- One card is flipped face-up to start the **discard pile**.
- The remaining cards form the **stock** (pioche).
- The **dealer rotates** each round; the player **after the dealer** starts.
- (Physical "cut the deck" step is cosmetic; engine just shuffles with a seed.)

### 3.4 The 11 rounds (contracts)

Each round has a mandatory **contract**. To go out ("sortir"), a player must
lay down the contract **and** the cards laid must total **≥ 40 points**.

| Round | Contract |
|---|---|
| 1 | 1 triplet |
| 2 | 1 run of 4 |
| 3 | 1 run of 5 |
| 4 | 2 triplets |
| 5 | 1 run of 4 + 1 triplet |
| 6 | 2 runs of 4 |
| 7 | 3 triplets |
| 8 | 2 triplets + 1 run of 4 |
| 9 | 2 runs of 4 + 1 triplet |
| 10 | 3 runs of 4 |
| 11 | 3 triplets + 1 run of 4 |

- **Triplet** = ≥3 cards of the same rank (e.g. `7♠ 7♥ 7♦`).
- **Run** = ≥3 consecutive cards of the **same suit** (e.g. `4♠ 5♠ 6♠ 7♠`).
- "Run of 4" / "run of 5" set a **minimum length** for the contract meld.

### 3.5 A turn

A turn is a small state machine. In order:

1. **Draw** — take exactly one card, from **stock** *or* the **discard top**.
2. **Meld / lay off** (optional, except special cases below) — lay melds and/or
   extend existing melds.
3. **Discard** — drop exactly one card onto the discard pile. The turn **always**
   ends with a discard.

### 3.6 Special rule — drawing from the discard

- If you take the **face-up discard**, you are **obliged to immediately lay a
  valid combination that uses that card**.
- You may **not** take the discard and then simply discard without melding.
- (Drawing from the stock carries no such obligation.)

### 3.7 Free card ("carte gratuite")

A refused face-up discard can be claimed *for free* by another player.

**2 players**

- On the **first turn**, the starting player may take the face-up card or refuse.
- If they **take** it, they must **go out immediately** (contract + ≥40 pts).
- If they **refuse**, the other player may take it **for free** — with no
  obligation to go out.

**3+ players**

- When a player refuses the face-up card, the **following players** may claim it
  for free.
- This can chain: a player may pick up several free cards in succession, so a
  hand can temporarily exceed 13 cards.

> **Confirmed model.** A refused face-up card may be claimed **only at the moment
> it is refused** — not picked up later. Claiming a free card **costs no discard**
> and does **not** consume your turn; you simply gain the card. Each player may
> take **at most one free card per turn**. (Across turns this is how a hand can
> grow past 13 cards.)

### 3.8 Going out ("sortir") & laying off

- **The first going-out is a single action.** You must lay the **round's
  contract** and the cards laid must total **≥ 40 points**. The contract cannot
  be assembled piecemeal across turns — it all goes down at once. (You may lay
  extra supplementary combinations in the same action; they count toward the 40.)
- **After you have gone out** you typically still hold cards. On your
  **subsequent turns** you progressively shed them under the base rules:
  - **Supplementary combinations** — additional triplets / runs of ≥3 (§3.4).
  - **Laying off** — adding cards onto **your own or others'** existing melds.
  - **Triplet evolution** — completing missing suits, then the 2nd-deck copies
    (§3.9).
- You cannot meld or lay off **before** you have gone out.

### 3.9 Jokers

- A joker substitutes for **any** card. **No limit** per meld.
- **In triplets**, a joker represents the **exact missing card**.
  - `7♠ 7♥ Joker` → the joker is "the 7♦ or 7♣".
  - If someone adds the `7♦`, the joker **auto-becomes the 7♣** and is **not yet
    recoverable**.
- **Joker recovery:** a joker can be reclaimed into a hand **only** by laying the
  **exact card it currently represents**.
  - `7♠ 7♥ 7♦ Joker` (joker = 7♣). A player who lays the real `7♣` **takes the
    joker** into their hand.
- **Triplet evolution:** a triplet can grow by adding the missing suits; once all
  4 suits are present, you may keep adding identical rank cards from the **second
  deck**.

### 3.10 Scoring

- A round ends when a player has **laid all their cards and discards their last
  card** (hand becomes empty after the final discard).
- The player who went out scores **0** for the round.
- Every other player sums the **point value of the cards still in their hand**
  (§3.2). Jokers in hand are a punishing **25** each.
- After **11 rounds**, totals are summed. **Lowest total wins.**

---

## 4. Rules clarifications

### 4.1 Resolved (confirmed by the rules owner)

| # | Question | Ruling |
|---|---|---|
| R1 | Deck composition | **110 cards** — two 52-card decks **+ 6 jokers**. "108" in the PDF is a typo. |
| R2 | Free-card chain — timing | A refused face-up card is claimable **only at the moment of refusal**, never later. |
| R3 | Free-card chain — cost | Claiming **costs no discard** and does not consume the turn. |
| R4 | Free-card chain — cap | **At most one free card per player per turn.** |
| R5 | Going out | The **first sortie is a single action**: contract **+ ≥40 pts**, laid all at once (no partial contract across turns). |
| R6 | After going out | Remaining cards are shed on **later turns** via supplementary combinations, lay-offs, and triplet evolution (base rules). |
| R7 | 40-pt minimum — joker value | A joker laid in a meld counts toward the 40 as the **value of the card it represents** (not 25). |
| R8 | Joker in hand | A joker still in hand at round end scores a flat **25** (per the PDF). |

### 4.2 Still open (low-impact, sensible defaults in place)

These don't block anything; each sits behind a constant or strategy.

- **End-of-round timing** `[default]`: a round ends the instant a player sheds
  their last card — whether the last card is discarded or melded. Confirm there
  is no "must end on a discard to the pile" subtlety.
- **Stock exhaustion** `[default]`: when the stock empties, reshuffle the discard
  pile (keeping its top card face-up) into a fresh stock. (Not covered by the
  PDF.)

---

## 5. System architecture

```
            ┌──────────────────────────────────────────────┐
            │                   Browser                      │
            │   React + Vite + Tailwind + shadcn/ui          │
            │                                                │
            │   ┌──────────────┐      ┌──────────────────┐   │
            │   │ UI components │◄────►│  Game store (zustand) │
            │   └──────────────┘      └─────────┬────────┘   │
            │                                   │            │
            │                       ┌───────────▼─────────┐  │
            │                       │  WebSocket client    │  │
            │                       └───────────┬─────────┘  │
            └───────────────────────────────────┼───────────┘
                                                 │  JSON intents / events
                                          (WebSocket, wss://)
                                                 │
            ┌────────────────────────────────────▼───────────┐
            │              FastAPI server (uvicorn)            │
            │                                                  │
            │  HTTP (REST)            WebSocket (/ws/table/{id})│
            │  ┌───────────────┐      ┌──────────────────────┐ │
            │  │ tables/router │      │  realtime/ws endpoint │ │
            │  │  create/join  │      │  connection manager   │ │
            │  └───────┬───────┘      └───────────┬──────────┘ │
            │          │                          │            │
            │          ▼                          ▼            │
            │  ┌─────────────────────────────────────────────┐│
            │  │              TableManager (in-mem)           ││
            │  │  table_id → GameSession (lock + state)       ││
            │  └─────────────────────┬───────────────────────┘│
            │                        ▼                         │
            │  ┌─────────────────────────────────────────────┐│
            │  │         game engine (pure, side-effect-free) ││
            │  │  apply(state, intent) -> (state, events)     ││
            │  └─────────────────────────────────────────────┘│
            └──────────────────────────────────────────────────┘
```

### Request/response model

- **REST** is used only for *pre-game* lifecycle: create table, join table
  (returns room code + a per-player session token), list public tables.
- **WebSocket** carries everything *in-game*: a client opens
  `wss://…/ws/table/{table_id}?token=…`, the server places that socket in the
  table's connection group, and:
  - client → server: **intents** (`draw_stock`, `draw_discard`, `meld`,
    `lay_off`, `discard`, `claim_free_card`, `ready`, …).
  - server → client: **events** + an authoritative, **per-seat-redacted**
    snapshot (you receive your own hand; opponents are reduced to hand *counts*).

### Concurrency model

- Each table is a `GameSession` guarded by an `asyncio.Lock`. Intents are applied
  one at a time, so the pure engine never sees concurrent mutation.
- The engine is synchronous and pure; the async layer only does I/O (broadcast,
  persistence later) around it.

### Reconnection (designed-for, hardened later)

- The join token identifies a *seat*, not a socket. Dropping and reopening the
  WebSocket with the same token re-attaches to the same seat and replays the
  current snapshot. v1 keeps the seat alive for a grace period; turn timeouts and
  abandonment handling are a later milestone.

---

## 6. Backend design (FastAPI, domain-first)

Per the modern-fastapi skill: `src/` layout, uv, Pydantic v2, versioned API
namespace, lifespan, structured logging, typed domain exceptions. **No service
layer / repository** unless justified — the game engine is the one rich
abstraction and it earns its place.

```
rami/                              # repo root
├── pyproject.toml                 # uv, ruff, mypy, pytest
├── DESIGN.md
├── docs/
└── src/rami/
    ├── main.py                    # app factory, middleware, lifespan, exc handlers
    ├── api/
    │   └── v1.py                  # aggregates REST routers
    ├── core/
    │   ├── config.py              # pydantic-settings get_settings()
    │   ├── logging.py             # JSON/dev logging + request middleware
    │   └── exceptions.py          # AppError base + domain exceptions
    ├── tables/                    # lobby / table lifecycle domain
    │   ├── router.py              # POST /tables, POST /tables/{id}/join, GET ...
    │   ├── schemas.py             # CreateTable, JoinTable, TableSummary ...
    │   ├── manager.py             # TableManager: id -> GameSession (in-mem)
    │   └── models.py              # (later) persistent table records
    ├── realtime/                  # WebSocket transport domain
    │   ├── ws.py                  # /ws/table/{id} endpoint
    │   ├── connections.py         # ConnectionManager (per-table socket groups)
    │   └── protocol.py            # Pydantic models for intents & events
    └── game/                      # the pure rules engine (no I/O)
        ├── cards.py               # Card, Suit, Rank, deck building, values
        ├── melds.py               # Meld types, validation, joker logic
        ├── contracts.py           # the 11-round contract table + checkers
        ├── state.py               # GameState, PlayerState, Phase enums
        ├── engine.py              # apply(state, intent) -> (state, [events])
        ├── scoring.py             # hand scoring, round/game totals
        └── intents.py             # Intent union (draw/meld/discard/...)
```

### Why a `game/` engine domain instead of CRUD

The hard part of this app is **the rules**, not the HTTP. Keeping `game/`
free of FastAPI, sockets, time, and randomness (the shuffle takes an injected
seed) means the entire rulebook is exhaustively unit-testable:

```python
# the heart of the engine — pure, deterministic
def apply(state: GameState, intent: Intent) -> tuple[GameState, list[Event]]:
    """Validate `intent` against `state`, return the next state and the
    events to broadcast. Raises IllegalMove (an AppError) if invalid.
    Never mutates `state` in place."""
```

The `realtime` layer is a thin shell: receive JSON → parse into an `Intent`
(Pydantic) → acquire the table lock → `apply(...)` → persist (later) → broadcast
redacted snapshots + events. Domain errors (`IllegalMove`, `NotYourTurn`,
`ContractNotMet`) inherit from `AppError` and map to either a WS error event or
an HTTP 4xx via the centralized handler.

### Key engine types (sketch)

```python
class Suit(StrEnum):  SPADES="S"; HEARTS="H"; DIAMONDS="D"; CLUBS="C"
class Phase(StrEnum): LOBBY; DEAL; AWAIT_DRAW; AWAIT_MELD; AWAIT_DISCARD; \
                      ROUND_OVER; GAME_OVER

@dataclass(frozen=True)
class Card:
    suit: Suit | None      # None for a joker
    rank: int | None       # 1..14; None for a joker
    is_joker: bool = False
    deck_id: int = 0       # 0/1 — which physical deck (for 2nd-deck rules)

@dataclass
class Meld:
    kind: Literal["triplet", "run"]
    cards: list[Card]                 # jokers carry their *represented* card
    owner_seat: int

@dataclass
class GameState:
    round_no: int                     # 1..11
    phase: Phase
    dealer_seat: int
    turn_seat: int
    stock: list[Card]
    discard: list[Card]
    seats: list[PlayerState]          # hand, melds-down flag, score
    table_melds: list[Meld]
    contract: Contract                # derived from round_no
    rng_seed: int
```

### Logging & errors (per skill)

- `core/logging.py` configures JSON-in-prod / readable-in-dev, level from
  settings; a request-logging middleware records method/path/status/duration.
- Module-level `logger = logging.getLogger(__name__)` everywhere; ~2 log lines
  per handler (domain event + outcome). Never log hands, tokens, or full
  payloads.
- `AppError` → `core/exceptions.py`; centralized `@app.exception_handler` maps
  domain errors to responses. `HTTPException` reserved for genuine HTTP concerns.

### Definition of done (gates)

`uv run ruff check .` · `uv run ruff format --check .` · `uv run mypy src/` ·
`uv run pytest -x`. Coverage gate switched on once the first engine slice +
tests exist.

---

## 7. WebSocket protocol

JSON messages, discriminated by a `type` field. All modelled as Pydantic v2
unions in `realtime/protocol.py`.

### Client → server (intents)

| `type` | Payload | Notes |
|---|---|---|
| `ready` | — | Mark seat ready in lobby |
| `draw_stock` | — | Draw top of stock |
| `draw_discard` | — | Take face-up discard (obliges an immediate meld) |
| `claim_free_card` | — | Claim a refused discard for free |
| `meld` | `groups: Card[][]` | Lay one or more melds (contract or extra) |
| `lay_off` | `meld_id, cards` | Extend an existing table meld (post-going-out) |
| `recover_joker` | `meld_id, card` | Lay the exact card a joker represents, take joker |
| `discard` | `card` | Drop one card; ends the turn |
| `sort_hand` | `order` | Client-only convenience; server may ignore/echo |

### Server → client (events + state)

| `type` | Payload |
|---|---|
| `snapshot` | Full per-seat-redacted `GameState` view (sent on connect & after each change) |
| `turn_changed` | `seat`, `phase` |
| `card_drawn` | `seat`, `source` (`stock`/`discard`), card only if it's you |
| `meld_laid` | `seat`, `meld` |
| `laid_off` | `seat`, `meld_id`, `cards` |
| `discarded` | `seat`, `card` |
| `free_card_offered` / `free_card_claimed` | `seat` |
| `round_scored` | per-seat round points + running totals |
| `game_over` | final standings |
| `error` | `code`, `message` (e.g. `ILLEGAL_MOVE`, `NOT_YOUR_TURN`) |

**Redaction:** the `snapshot` sent to seat *N* contains seat *N*'s full hand and,
for every other seat, only `hand_count`. The stock is a count; the discard pile
shows its top card (and optionally full pile for UX).

---

## 8. Frontend design (React + Vite + Tailwind + shadcn/ui)

```
web/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── components.json                # shadcn/ui config
└── src/
    ├── main.tsx
    ├── App.tsx                     # router: Home / Table
    ├── lib/
    │   ├── ws.ts                   # typed WebSocket client (reconnect, heartbeat)
    │   └── api.ts                  # REST: create/join table
    ├── store/
    │   └── game.ts                 # zustand store: snapshot, selectors, intents
    ├── types/
    │   └── protocol.ts             # shared types mirroring backend protocol
    ├── pages/
    │   ├── Home.tsx                # create / join table
    │   └── Table.tsx               # the game table
    └── components/
        ├── ui/                     # shadcn/ui primitives (button, card, dialog…)
        ├── table/
        │   ├── GameTable.tsx       # felt surface + layout of all seats
        │   ├── OpponentSeat.tsx    # avatar, name, hand-count, turn indicator
        │   ├── CenterArea.tsx      # stock + discard pile
        │   ├── TableMelds.tsx      # melds laid on the table
        │   ├── PlayerHand.tsx      # your hand (drag-and-drop, sortable)
        │   ├── PlayingCard.tsx     # one card (suit/rank/joker, faces)
        │   ├── ContractBanner.tsx  # current round + contract + "need 40 pts"
        │   ├── ActionBar.tsx       # context buttons: Draw / Meld / Discard
        │   └── Scoreboard.tsx      # per-round + total scores
        └── modals/
            ├── RoundEndDialog.tsx
            └── GameOverDialog.tsx
```

### State & data flow

- A single **zustand** store holds the latest `snapshot`. The WS client writes
  incoming events/snapshots into it; components subscribe via selectors.
- User actions dispatch **intents** through the WS client. The UI optimistically
  greys out illegal actions using local validators that *mirror* (never replace)
  server rules — the server remains authoritative.
- **Drag-and-drop** via `@dnd-kit/core` + `@dnd-kit/sortable`: reorder hand,
  drag cards into a "staging tray" to build a meld, drop onto a table meld to lay
  off.

### Key interactions

- **Draw:** click the stock or the discard top. Taking the discard opens the
  meld tray and won't let you finish your turn until a meld using that card is
  valid (mirrors §3.6).
- **Meld:** drag cards into the staging tray; the tray live-validates
  (triplet/run, contract satisfied, ≥40). "Lay down" enables only when legal.
- **Discard:** drag a card to the discard pile (or select + "Discard"), which
  ends the turn.
- **Joker affordances:** a joker on the table shows the rank/suit it currently
  represents; if you hold the exact card, a "recover joker" hint appears.

### Visual language

Modern, calm card-room aesthetic — a deep felt table, soft shadows, crisp white
cards with classic suit glyphs (red ♥♦, black ♠♣), a gold accent for "your
turn". Tailwind tokens + shadcn/ui primitives (Button, Card, Dialog, Tooltip,
Avatar, Badge, Sonner toasts). Fully responsive: the felt re-flows for tablet
and phone, hand becomes a fanned, scrollable strip on small screens. See
`mockups/index.html` for the concrete look.

---

## 9. Data & persistence

- **v1:** everything in memory in the single server process. A server restart
  ends in-flight games (acceptable for an MVP; tables are ephemeral).
- **Designed-for later:** swap `TableManager`'s in-memory dict for a store
  (Redis for live tables, Postgres for finished-game history/stats). The engine
  is already serialisable — `GameState` is plain dataclasses → JSON — so
  snapshotting/persisting is additive. Accounts, if added, slot into a new
  `users/` domain without touching `game/`.

---

## 10. Testing strategy

- **Engine (the bulk):** table-driven unit tests over `apply(state, intent)`.
  Cover every contract (rounds 1–11), joker representation/auto-reassignment/
  recovery, triplet evolution to the 2nd deck, the discard-pickup meld
  obligation, the free-card chain, the 40-point gate, Ace low/high/no-wrap, and
  scoring. Deterministic via injected RNG seed.
- **Transport:** a handful of async tests driving a WS client through a full
  short round.
- **Frontend:** component tests for the meld-tray validator and hand DnD;
  Playwright smoke test for create-table → play-a-turn.

---

## 11. Roadmap / milestones

1. **M0 — Scaffolding.** uv project (modern-fastapi golden slice), Vite + React
   + Tailwind + shadcn, CI gates green, hello-world WS round-trip.
2. **M1 — Engine core.** Cards, melds, contracts, scoring, turn state machine
   for a single round; full unit tests. *No UI yet.*
3. **M2 — One playable round end-to-end.** REST create/join, WS transport,
   redacted snapshots, the Table UI from the mockup, draw/meld/discard for
   round 1.
4. **M3 — Full game.** All 11 contracts, jokers (representation/recovery/
   evolution), free-card chain, going-out + lay-off, round/game scoring,
   round-end & game-over dialogs.
5. **M4 — Robustness.** Reconnection, turn timers, abandonment, stock-exhaustion
   reshuffle, spectator-safe redaction review.
6. **M5 (post-v1).** Accounts + history, persistence, AI bots, matchmaking/public
   lobbies.

---

## 12. Tech stack summary

| Layer | Choice |
|---|---|
| Language (server) | Python 3.12+ |
| Web framework | FastAPI + uvicorn |
| Realtime | WebSockets (native FastAPI) |
| Validation | Pydantic v2 / pydantic-settings |
| Package mgr | uv |
| Lint/format/type/test | ruff · mypy · pytest |
| Language (client) | TypeScript |
| Build | Vite |
| UI | React (latest) + Tailwind + shadcn/ui |
| Client state | zustand |
| Drag & drop | @dnd-kit |
| Toasts/feedback | sonner (shadcn) |

---

## 13. Open questions for you

The four major rules ambiguities are now **resolved** (see §4.1). Only minor
items remain:

1. **§4.2** End-of-round timing — confirm a round ends the instant a player
   sheds their last card (discarded *or* melded), with no "must end on a
   discard" subtlety.
2. **§4.2** Stock exhaustion — OK to reshuffle the discard pile (minus its
   face-up top card) into a fresh stock when the stock runs out?
3. Any other house rules not in the PDF (penalties, "buy" mechanics, etc.)?
