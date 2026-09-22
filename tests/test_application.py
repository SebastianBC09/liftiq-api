"""HTTP contracts and application ownership of configuration/infrastructure."""

from typing import Annotated
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_current_user_id, get_db
from app.core.exceptions import ConflictError, EntityNotFoundError, UnauthorizedError
from app.core.security import AccessTokens
from app.main import create_app


class Credentials(BaseModel):
    password: str = Field(min_length=8)


@pytest.mark.parametrize(
    ("exception", "status", "code"),
    [
        (ConflictError("Already exists"), 409, "conflict"),
        (EntityNotFoundError("User", "unknown"), 404, "not_found"),
        (UnauthorizedError("private diagnostic"), 401, "unauthorized"),
    ],
)
async def test_domain_errors(
    app: FastAPI, client: AsyncClient, exception: Exception, status: int, code: str
) -> None:
    @app.get("/test-error")
    async def fail():
        raise exception

    response = await client.get("/test-error")
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "private diagnostic" not in response.text
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


async def test_validation_does_not_echo_password(app: FastAPI, client: AsyncClient) -> None:
    @app.post("/test-validation")
    async def validate(body: Credentials):
        return {"accepted": True}

    response = await client.post("/test-validation", json={"password": "secret"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["errors"][0]["field"] == ["body", "password"]
    assert "secret" not in response.text
    assert "input" not in response.json()["errors"][0]


async def test_bearer_contract(app: FastAPI, client: AsyncClient, settings: Settings) -> None:
    @app.get("/test-protected")
    async def protected(subject: Annotated[str, Depends(get_current_user_id)]):
        return {"id": subject}

    for header in ({}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic abc"}):
        response = await client.get("/test-protected", headers=header)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    token = AccessTokens(settings).create("user-123")
    response = await client.get("/test-protected", headers={"Authorization": f"Bearer {token}"})
    assert response.json() == {"id": "user-123"}


async def test_cors(client: AsyncClient) -> None:
    headers = {
        "Origin": "http://localhost:8100",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    allowed = await client.options("/health", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == headers["Origin"]
    denied = await client.options(
        "/health", headers=headers | {"Origin": "https://untrusted.example"}
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.parametrize("fail", [False, True])
async def test_lifespan_disposes_engine(settings: Settings, fail: bool) -> None:
    app = create_app(settings)
    assert not hasattr(app.state, "database")
    with patch("app.db.session.Database.dispose", new_callable=AsyncMock) as dispose:
        try:
            async with app.router.lifespan_context(app):
                assert hasattr(app.state, "database")
                if fail:
                    raise RuntimeError("shutdown")
        except RuntimeError:
            pass
        dispose.assert_awaited_once()


def test_application_settings_are_isolated(settings: Settings) -> None:
    first = create_app(settings)
    other = settings.model_copy(
        update={"secret_key": settings.secret_key, "access_token_expire_minutes": 5}
    )
    second = create_app(other)
    assert first.state.settings.access_token_expire_minutes == 15
    assert second.state.settings.access_token_expire_minutes == 5


async def test_request_session_rolls_back_on_failure(app: FastAPI, client: AsyncClient) -> None:
    async with app.state.database.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE request_entry (id INTEGER PRIMARY KEY)"))

    @app.post("/test-rollback")
    async def fail(session: Annotated[AsyncSession, Depends(get_db)]) -> None:
        await session.execute(text("INSERT INTO request_entry VALUES (1)"))
        raise ConflictError("Abort request")

    response = await client.post("/test-rollback")
    assert response.status_code == 409
    async with app.state.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM request_entry")) == 0


async def test_startup_does_not_create_schema(app: FastAPI, client: AsyncClient) -> None:
    async with app.state.database.session() as session:
        assert (
            await session.scalar(text("SELECT count(*) FROM sqlite_master WHERE type='table'")) == 0
        )
