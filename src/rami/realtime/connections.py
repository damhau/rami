"""Tracks the live WebSocket per seat for each table."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._by_code: dict[str, dict[int, WebSocket]] = {}

    def register(self, code: str, seat: int, ws: WebSocket) -> None:
        self._by_code.setdefault(code, {})[seat] = ws

    def unregister(self, code: str, seat: int, ws: WebSocket) -> None:
        seats = self._by_code.get(code)
        if seats and seats.get(seat) is ws:
            del seats[seat]
            if not seats:
                self._by_code.pop(code, None)

    def connected_seats(self, code: str) -> list[int]:
        return list(self._by_code.get(code, {}))

    async def send(self, code: str, seat: int, payload: dict[str, Any]) -> None:
        ws = self._by_code.get(code, {}).get(seat)
        if ws is not None:
            await ws.send_json(payload)

    async def broadcast(self, code: str, payload: dict[str, Any]) -> None:
        for ws in list(self._by_code.get(code, {}).values()):
            await ws.send_json(payload)
