"""Isolated settings and application lifespan; never read a developer's dotenv."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from alembic import command
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Remove deployment env overrides and supply test-only configuration."""
    for name in list(os.environ):
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)
    return Settings(
        _env_file=None,
        secret_key="test-only-signing-secret-at-least-64-bytes-for-token-validation-tests",
        database_url="sqlite+aiosqlite:///:memory:",
        environment="test",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@pytest.fixture
def migrated_db_path(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every domain integration test starts with the actual Alembic schema."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "auth.db"
    monkeypatch.setenv("SECRET_KEY", settings.secret_key.get_secret_value())
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    return path
