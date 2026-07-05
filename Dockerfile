# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the React frontend
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build        # outputs /web/dist


# ---------------------------------------------------------------------------
# Stage 2 — Python backend that also serves the built SPA
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Install dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

# The built frontend from stage 1, served from "/" by FastAPI.
COPY --from=frontend /web/dist ./web/dist

ENV PATH="/app/.venv/bin:$PATH" \
    RAMI_ENV=prod \
    RAMI_LOG_LEVEL=INFO \
    RAMI_STATIC_DIR=/app/web/dist

EXPOSE 8000

# Single process: the table/game state is held in memory, so do NOT scale to
# multiple workers (each would have its own, divergent state).
CMD ["uvicorn", "rami.main:app", "--host", "0.0.0.0", "--port", "8000"]
