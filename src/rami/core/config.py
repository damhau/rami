"""Application settings, exposed through the cached `get_settings` dependency."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAMI_", env_file=".env", extra="ignore")

    ENV: str = "dev"  # "dev" | "prod"
    LOG_LEVEL: str = "INFO"

    # When set to a built frontend directory (web/dist), the app also serves the
    # SPA from "/". Used by the Docker image; unset in local dev (Vite serves it).
    STATIC_DIR: str | None = None

    # CORS — the Vite dev server origins allowed to call the API / open WS.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Gameplay
    MIN_PLAYERS: int = 2
    MAX_PLAYERS: int = 4
    GO_OUT_MIN_POINTS: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
