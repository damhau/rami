"""The in-game WebSocket endpoint.

A client opens ``/ws/table/{code}?token=...``; the token identifies its seat.
Each inbound message is parsed, applied to the table's authoritative state under
the session lock, and the result is broadcast as a *per-seat redacted* snapshot
(you see your own hand, opponents only as counts) plus an events stream.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from rami.core.exceptions import AppError, IllegalMove, TableState
from rami.game import ai
from rami.game.state import Event, GameState, Phase
from rami.tables.manager import GameSession, TableManager

from . import protocol as P
from .connections import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()
connections = ConnectionManager()

# Pause between bot moves so a human can follow the play unfold.
BOT_MOVE_DELAY_S = 0.7
# Auto-play a seat that doesn't act in time. A disconnected player is covered
# quickly so the table isn't stalled; a connected-but-idle player gets a long
# grace period before the bot plays their turn.
TURN_TIMEOUT_S = 150.0
DISCONNECT_TIMEOUT_S = 25.0
# A pending free-card decision holds the drawer (issue #10), so a connected human
# gets a shorter — but comfortable — window to claim before the offer auto-resolves
# and the table moves on.
FREE_CARD_TIMEOUT_S = 30.0
AUTOPLAY_STEP_S = 0.5
_TURN_PHASES = {Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD}

# One pending idle timer per table (cancelled/replaced on every state change).
_idle_tasks: dict[str, asyncio.Task[None]] = {}


def _manager(ws: WebSocket) -> TableManager:
    manager: TableManager = ws.app.state.table_manager
    return manager


def _build_all(session: GameSession) -> dict[int, dict[str, Any]]:
    """Build the redacted snapshot dict for every seat (call under the lock)."""
    assert session.state is not None
    connected = [s.connected for s in session.seats]
    ready = [s.ready for s in session.seats]
    bots = [s.is_bot for s in session.seats]
    return {
        p.seat: P.build_snapshot(
            session.code, session.state, p.seat, connected, ready, bots
        ).model_dump()
        for p in session.state.players
    }


async def _send_all(code: str, snaps: dict[int, dict[str, Any]]) -> None:
    for seat, snap in snaps.items():
        await connections.send(code, seat, snap)


async def _broadcast(session: GameSession, events: list[Event]) -> None:
    """Build snapshots (under lock), send them, and stream events."""
    async with session.lock:
        snaps = _build_all(session)
    await _send_all(session.code, snaps)
    if events:
        await connections.broadcast(session.code, P.events_payload(events).model_dump())


def _bot_seat_to_act(session: GameSession, state: GameState) -> int | None:
    """The bot seat that should move now (a free-card decider, else the turn
    seat), or None if it is a human's move."""
    offer = state.free_card
    if offer is not None and offer.pending_seats:
        head = offer.pending_seats[0]
        # A bot at the head of the offer decides its own free card. A *human* at
        # the head must be given time to react (issue #10): pause here — do not let
        # the bot drawer rush ahead and discard, which would close the offer before
        # the human can claim it.
        return head if session.seats[head].is_bot else None
    if state.phase in _TURN_PHASES and session.seats[state.turn_seat].is_bot:
        return state.turn_seat
    return None


async def _run_bots(session: GameSession) -> None:
    """Advance any bot moves until it is a human's turn again, broadcasting each
    step with a short delay for readability."""
    if not session.has_bots:
        return
    while True:
        async with session.lock:
            state = session.state
            if state is None:
                return
            seat = _bot_seat_to_act(session, state)
            if seat is None:
                return
            intent = ai.next_bot_intent(state, seat)
            if intent is None:
                return
            try:
                events = session.apply(intent)
            except AppError:
                logger.exception("bot.move_failed", extra={"code": session.code, "seat": seat})
                return
        await _broadcast(session, events)
        await asyncio.sleep(BOT_MOVE_DELAY_S)


# --------------------------------------------------------------------------- #
# Turn timeout / abandonment: auto-play a human seat that doesn't act in time
# --------------------------------------------------------------------------- #


def _seat_is_awaited(session: GameSession, seat: int) -> bool:
    """True if the table is currently waiting on `seat` to act — either it holds a
    pending free-card decision at the head of the offer, or it is its turn."""
    state = session.state
    if state is None:
        return False
    offer = state.free_card
    if offer is not None and offer.pending_seats:
        return offer.pending_seats[0] == seat
    return state.phase in _TURN_PHASES and state.turn_seat == seat


def _waiting_human_seat(session: GameSession) -> int | None:
    """The human seat the game is waiting on, or None. A pending free-card
    decision takes priority over the turn seat (issue #10): while a human is being
    offered the refused discard, the whole table — including the bot drawer — is
    waiting on that decision."""
    state = session.state
    if state is None:
        return None
    offer = state.free_card
    if offer is not None and offer.pending_seats:
        head = offer.pending_seats[0]
        return head if not session.seats[head].is_bot else None
    if state.phase not in _TURN_PHASES:
        return None
    ts = state.turn_seat
    if ts < len(session.seats) and not session.seats[ts].is_bot:
        return ts
    return None


async def _auto_play_seat(session: GameSession, seat: int) -> None:
    """Play the bot policy on behalf of an idle/absent seat until the table no
    longer waits on it (its turn ends, or its free-card decision is made)."""
    while True:
        async with session.lock:
            state = session.state
            if state is None or not _seat_is_awaited(session, seat):
                return
            intent = ai.next_bot_intent(state, seat)
            if intent is None:
                return
            try:
                events = session.apply(intent)
            except AppError:
                logger.exception("autoplay.failed", extra={"code": session.code, "seat": seat})
                return
        await _broadcast(session, events)
        await asyncio.sleep(AUTOPLAY_STEP_S)


async def _idle_timeout(session: GameSession, seat: int, nonce: int, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return
    async with session.lock:
        if session.decision_nonce != nonce or not _seat_is_awaited(session, seat):
            return
    logger.info("turn.autoplay", extra={"code": session.code, "seat": seat})
    await _auto_play_seat(session, seat)
    await _advance(session)


def _schedule_idle(session: GameSession) -> None:
    prev = _idle_tasks.pop(session.code, None)
    if prev is not None:
        prev.cancel()
    seat = _waiting_human_seat(session)
    if seat is None:
        return
    state = session.state
    awaiting_free_card = (
        state is not None and state.free_card is not None and bool(state.free_card.pending_seats)
    )
    if not session.seats[seat].connected:
        delay = DISCONNECT_TIMEOUT_S
    elif awaiting_free_card:
        delay = FREE_CARD_TIMEOUT_S
    else:
        delay = TURN_TIMEOUT_S
    task = asyncio.create_task(_idle_timeout(session, seat, session.decision_nonce, delay))
    _idle_tasks[session.code] = task
    task.add_done_callback(
        lambda t: _idle_tasks.pop(session.code, None) if _idle_tasks.get(session.code) is t else None
    )


async def _advance(session: GameSession) -> None:
    """After any change: let the bots act, then arm the idle timer for whoever
    the table is now waiting on."""
    await _run_bots(session)
    _schedule_idle(session)


def _process(session: GameSession, seat: int, msg: P.ClientMessage) -> list[Event]:
    """Apply one client message (call under the lock)."""
    if isinstance(msg, P.StartMsg):
        if seat != 0:
            raise TableState("only the host can start the game")
        return session.start()
    if isinstance(msg, P.NextRoundMsg):
        if seat != 0:
            raise TableState("only the host can start the next round")
        return session.next_round()
    if isinstance(msg, P.ReadyMsg):
        session.set_ready(seat, msg.ready)
        return []
    intent = P.to_engine_intent(seat, msg)
    if intent is None:
        raise IllegalMove("unsupported message")
    return session.apply(intent)


@router.websocket("/ws/table/{code}")
async def table_ws(websocket: WebSocket, code: str, token: str = "") -> None:
    manager = _manager(websocket)
    try:
        session = manager.get(code)
    except AppError:
        await websocket.close(code=4404)
        return
    seat = session.seat_for_token(token)
    if seat is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    seat.connected = True
    connections.register(session.code, seat.seat, websocket)
    logger.info("ws.connected", extra={"code": session.code, "seat": seat.seat})
    await _broadcast(session, [])
    # Bots may need to act (solo game), and arm the idle timer for a human turn.
    await _advance(session)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = P.client_message_adapter.validate_json(raw)
            except ValidationError as exc:
                await websocket.send_json(
                    P.ErrorMsg(code="bad_message", message=str(exc)).model_dump()
                )
                continue
            try:
                async with session.lock:
                    events = _process(session, seat.seat, msg)
            except AppError as exc:
                await websocket.send_json(
                    P.ErrorMsg(code=exc.code, message=exc.message).model_dump()
                )
                continue
            await _broadcast(session, events)
            await _advance(session)
    except WebSocketDisconnect:
        logger.info("ws.disconnected", extra={"code": session.code, "seat": seat.seat})
    finally:
        # Only mark disconnected if a newer socket hasn't already claimed the seat.
        if connections.unregister(session.code, seat.seat, websocket):
            seat.connected = False
            await _broadcast(session, [])
            await _advance(session)  # switch to the shorter disconnected timeout
