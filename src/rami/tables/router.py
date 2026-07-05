"""REST endpoints for the pre-game table lifecycle: create, join, inspect."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from .dependencies import Manager
from .manager import GameSession, Seat
from .schemas import (
    CreateSoloRequest,
    CreateTableRequest,
    JoinedTable,
    JoinTableRequest,
    SeatInfo,
    TableSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tables", tags=["tables"])


def _seat_infos(session: GameSession) -> list[SeatInfo]:
    return [
        SeatInfo(seat=s.seat, name=s.name, connected=s.connected, ready=s.ready)
        for s in session.seats
    ]


def _joined(session: GameSession, seat: Seat) -> JoinedTable:
    return JoinedTable(
        code=session.code,
        seat=seat.seat,
        token=seat.token,
        host=seat.seat == 0,
        players=_seat_infos(session),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_table(payload: CreateTableRequest, manager: Manager) -> JoinedTable:
    logger.info("tables.create.requested", extra={"player_name": payload.name})
    session, host = manager.create(payload.name)
    logger.info("tables.create.succeeded", extra={"code": session.code})
    return _joined(session, host)


@router.post("/solo", status_code=status.HTTP_201_CREATED)
async def create_solo(payload: CreateSoloRequest, manager: Manager) -> JoinedTable:
    logger.info("tables.solo.requested", extra={"bots": payload.bots})
    session, host = manager.create_solo(payload.name, payload.bots)
    logger.info("tables.solo.succeeded", extra={"code": session.code})
    return _joined(session, host)


@router.post("/{code}/join")
async def join_table(code: str, payload: JoinTableRequest, manager: Manager) -> JoinedTable:
    logger.info("tables.join.requested", extra={"code": code})
    session, seat = manager.join(code, payload.name)
    logger.info("tables.join.succeeded", extra={"code": session.code, "seat": seat.seat})
    return _joined(session, seat)


@router.get("/{code}")
async def get_table(code: str, manager: Manager) -> TableSummary:
    session = manager.get(code)
    phase = session.state.phase.value if session.state is not None else "lobby"
    return TableSummary(
        code=session.code,
        phase=phase,
        players=_seat_infos(session),
        max_players=session.max_players,
    )
