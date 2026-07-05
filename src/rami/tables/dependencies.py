"""Dependencies for the tables domain."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .manager import TableManager


def get_manager(request: Request) -> TableManager:
    manager: TableManager = request.app.state.table_manager
    return manager


Manager = Annotated[TableManager, Depends(get_manager)]
