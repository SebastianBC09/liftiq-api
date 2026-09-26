# Resolve dependencies from the committed lockfile in the builder only.
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/seed_exercises.py ./scripts/seed_exercises.py

FROM python:3.13-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app
COPY --chmod=755 scripts/start.sh /usr/local/bin/liftiq-start
RUN mkdir -p /app/data && chown appuser:appuser /app/data
ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL="sqlite+aiosqlite:////app/data/liftiq.db" \
    ENVIRONMENT="production"
USER appuser
EXPOSE 8000
CMD ["liftiq-start"]
