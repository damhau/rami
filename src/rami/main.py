"""Application factory: wiring, middleware, lifespan, and routers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rami.api.v1 import api_router
from rami.core.config import get_settings, get_version
from rami.core.exceptions import register_exception_handlers
from rami.core.logging import RequestLoggingMiddleware, configure_logging
from rami.realtime.ws import router as ws_router
from rami.tables.manager import TableManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL, settings.ENV)
    app.state.table_manager = TableManager(settings.MIN_PLAYERS, settings.MAX_PLAYERS)
    logger.info("app.startup", extra={"env": settings.ENV})
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Rami Portugais", version=get_version(), lifespan=lifespan)

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(ws_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/version", tags=["meta"])
    async def version() -> dict[str, str]:
        return {"version": get_version()}

    # Serve the built SPA from "/" when configured (production / Docker). Mounted
    # last so /api, /ws and /health keep priority over the catch-all.
    if settings.STATIC_DIR and Path(settings.STATIC_DIR).is_dir():
        app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="spa")
        logger.info("app.static_mounted", extra={"dir": settings.STATIC_DIR})

    return app


app = create_app()
