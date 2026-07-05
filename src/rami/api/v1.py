"""Aggregates the versioned REST routers."""

from __future__ import annotations

from fastapi import APIRouter

from rami.tables.router import router as tables_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(tables_router)
