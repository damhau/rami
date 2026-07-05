"""Wire schemas for the table-lifecycle REST endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateTableRequest(BaseModel):
    name: str = Field(min_length=1, max_length=24)


class CreateSoloRequest(BaseModel):
    name: str = Field(min_length=1, max_length=24)
    bots: int = Field(default=1, ge=1, le=3)


class JoinTableRequest(BaseModel):
    name: str = Field(min_length=1, max_length=24)


class SeatInfo(BaseModel):
    seat: int
    name: str
    connected: bool
    ready: bool


class JoinedTable(BaseModel):
    """Returned to a player who created or joined a table — includes their
    private session token used to open the WebSocket."""

    code: str
    seat: int
    token: str
    host: bool
    players: list[SeatInfo]


class TableSummary(BaseModel):
    code: str
    phase: str
    players: list[SeatInfo]
    max_players: int
