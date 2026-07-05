"""Typed domain exceptions and their central HTTP mapping.

Domain code (including the pure game engine) raises `AppError` subclasses; it
never raises `HTTPException`. `register_exception_handlers` maps them to JSON
responses. The realtime layer reuses the same exceptions and turns them into WS
`error` events.

This module deliberately avoids importing FastAPI at the top level so the engine
can depend on the exception types without dragging in the web framework.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for all domain errors. `code` is a stable machine string."""

    code: str = "app_error"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        self.message = message or (self.__class__.__doc__ or self.code).strip()
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found."""

    code = "not_found"
    status_code = 404


class TableNotFound(NotFoundError):
    """No table exists for that code."""

    code = "table_not_found"


class TableFull(AppError):
    """This table already has the maximum number of players."""

    code = "table_full"
    status_code = 409


class TableState(AppError):
    """The table is not in a state that allows this action."""

    code = "table_state"
    status_code = 409


class IllegalMove(AppError):
    """The requested move is not legal in the current game state."""

    code = "illegal_move"
    status_code = 422


class NotYourTurn(IllegalMove):
    """It is not this player's turn."""

    code = "not_your_turn"


class ContractNotMet(IllegalMove):
    """The laid melds do not satisfy the round contract / minimum points."""

    code = "contract_not_met"


def register_exception_handlers(app: FastAPI) -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        logger.warning("domain.error", extra={"code": exc.code, "detail": exc.message})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
