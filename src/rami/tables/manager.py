"""In-memory tables. Each `GameSession` owns one game's authoritative state,
guarded by an asyncio lock so intents apply one at a time."""

from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass, field

from rami.core.exceptions import TableFull, TableNotFound, TableState
from rami.game import engine
from rami.game.intents import Intent
from rami.game.state import Event, GameState, Phase

logger = logging.getLogger(__name__)

CODE_LENGTH = 4


def _new_code() -> str:
    # A short, all-numeric code — easy to read aloud, type on a phone, or scan.
    return "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))


@dataclass
class Seat:
    seat: int
    name: str
    token: str
    connected: bool = False
    ready: bool = False


@dataclass
class GameSession:
    code: str
    min_players: int
    max_players: int
    seats: list[Seat] = field(default_factory=list)
    state: GameState | None = None
    seed: int = 0
    decision_nonce: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # -- lobby ------------------------------------------------------------- #

    @property
    def host_token(self) -> str:
        return self.seats[0].token if self.seats else ""

    def add_player(self, name: str) -> Seat:
        if self.state is not None and self.state.phase != Phase.LOBBY:
            raise TableState("the game has already started")
        if len(self.seats) >= self.max_players:
            raise TableFull()
        seat = Seat(seat=len(self.seats), name=name, token=secrets.token_urlsafe(16))
        self.seats.append(seat)
        self._rebuild_lobby_state()
        logger.info("table.player_joined", extra={"code": self.code, "seat": seat.seat})
        return seat

    def _rebuild_lobby_state(self) -> None:
        self.state = engine.new_game([s.name for s in self.seats], rng_seed=self.seed)

    def seat_for_token(self, token: str) -> Seat | None:
        return next((s for s in self.seats if s.token == token), None)

    def set_ready(self, seat: int, ready: bool) -> None:
        self.seats[seat].ready = ready

    def can_start(self) -> bool:
        return (
            self.state is not None
            and self.state.phase == Phase.LOBBY
            and len(self.seats) >= self.min_players
        )

    # -- game flow --------------------------------------------------------- #

    def start(self) -> list[Event]:
        if not self.can_start():
            raise TableState(f"need at least {self.min_players} players to start")
        assert self.state is not None
        self.state, events = engine.start_round(self.state)
        self.decision_nonce += 1
        logger.info("table.started", extra={"code": self.code, "players": len(self.seats)})
        return events

    def next_round(self) -> list[Event]:
        if self.state is None or self.state.phase != Phase.ROUND_OVER:
            raise TableState("no round to advance")
        self.state, events = engine.start_round(self.state)
        self.decision_nonce += 1
        return events

    def apply(self, intent: Intent) -> list[Event]:
        if self.state is None:
            raise TableState("game not started")
        self.state, events = engine.apply(self.state, intent)
        self.decision_nonce += 1
        return events


class TableManager:
    """Process-wide registry of live tables (in-memory, single instance)."""

    def __init__(self, min_players: int, max_players: int) -> None:
        self._tables: dict[str, GameSession] = {}
        self._min = min_players
        self._max = max_players

    def create(self, host_name: str) -> tuple[GameSession, Seat]:
        code = _new_code()
        while code in self._tables:
            code = _new_code()
        session = GameSession(
            code=code,
            min_players=self._min,
            max_players=self._max,
            seed=secrets.randbelow(2**31),
        )
        self._tables[code] = session
        host = session.add_player(host_name)
        logger.info("table.created", extra={"code": code})
        return session, host

    def get(self, code: str) -> GameSession:
        session = self._tables.get(code.upper())
        if session is None:
            raise TableNotFound()
        return session

    def join(self, code: str, name: str) -> tuple[GameSession, Seat]:
        session = self.get(code)
        seat = session.add_player(name)
        return session, seat

    def remove(self, code: str) -> None:
        self._tables.pop(code, None)
