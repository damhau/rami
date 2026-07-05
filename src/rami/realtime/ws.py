"""The in-game WebSocket endpoint.

A client opens ``/ws/table/{code}?token=...``; the token identifies its seat.
Each inbound message is parsed, applied to the table's authoritative state under
the session lock, and the result is broadcast as a *per-seat redacted* snapshot
(you see your own hand, opponents only as counts) plus an events stream.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from rami.core.exceptions import AppError, IllegalMove, TableState
from rami.game.state import Event
from rami.tables.manager import GameSession, TableManager

from . import protocol as P
from .connections import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()
connections = ConnectionManager()


def _manager(ws: WebSocket) -> TableManager:
    manager: TableManager = ws.app.state.table_manager
    return manager


def _build_all(session: GameSession) -> dict[int, dict[str, Any]]:
    """Build the redacted snapshot dict for every seat (call under the lock)."""
    assert session.state is not None
    connected = [s.connected for s in session.seats]
    ready = [s.ready for s in session.seats]
    return {
        p.seat: P.build_snapshot(session.code, session.state, p.seat, connected, ready).model_dump()
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
    except WebSocketDisconnect:
        logger.info("ws.disconnected", extra={"code": session.code, "seat": seat.seat})
    finally:
        seat.connected = False
        connections.unregister(session.code, seat.seat, websocket)
        await _broadcast(session, [])
