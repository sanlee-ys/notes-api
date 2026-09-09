# Lean serving image for the notes API.
# Single-stage: runtime deps are pure-Python wheels, so a multi-stage build
# would add complexity without shrinking much.
FROM python:3.14-slim

# Don't write .pyc files; flush stdout/stderr immediately so logs show up in
# Cloud Run without buffering.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Lockfile first so this layer is cached unless deps change. The package is
# copied next and imported via PYTHONPATH (same as local `--app-dir src`).
COPY pyproject.toml uv.lock ./
COPY src/notes_api ./src/notes_api

RUN uv sync --frozen --no-dev --no-install-project \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app

# Run as a non-root user. Standard hardening: if the process is compromised it
# isn't root inside the container.
USER appuser

# Cloud Run sends traffic to $PORT. Shell form so $PORT is expanded at runtime;
# fall back to 8081, the local default in the README.
EXPOSE 8081
CMD uv run --frozen --no-dev --no-sync uvicorn notes_api.main:app --host 0.0.0.0 --port ${PORT:-8081}
