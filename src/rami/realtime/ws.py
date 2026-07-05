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
_TURN_PHASES = {Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD}


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
        if session.seats[head].is_bot:
            return head
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
    # A solo game may already be waiting on the bots (they can act before the human).
    await _run_bots(session)

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
            await _run_bots(session)
    except WebSocketDisconnect:
        logger.info("ws.disconnected", extra={"code": session.code, "seat": seat.seat})
    finally:
        seat.connected = False
        connections.unregister(session.code, seat.seat, websocket)
        await _broadcast(session, [])
