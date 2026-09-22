"""Public auth contracts exercised against the real migrated database."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from app.core.refresh_tokens import hash_refresh_token
from app.core.security import AccessTokens, verify_password
from tests.auth_helpers import AUTH, ME, REGISTER, bearer, register
from tests.schema_helpers import connect


async def test_register_and_current_user(auth_client: AsyncClient, migrated_db_path: Path) -> None:
    response = await auth_client.post(
        f"{AUTH}/register", json=REGISTER | {"email": " PERSON@Example.COM ", "firstName": " Ada "}
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert set(data) == {"accessToken", "refreshToken", "tokenType", "expiresIn", "user"}
    assert data["expiresIn"] == 900 and data["tokenType"] == "bearer"
    assert set(data["user"]) == set(REGISTER) - {"password"} | {"id"}
    assert data["user"]["email"] == "person@example.com"
    assert data["user"]["firstName"] == "Ada"
    assert isinstance(data["user"]["heightCm"], float)
    profile = await auth_client.get(ME, headers=bearer(data))
    assert profile.status_code == 200 and profile.json() == data["user"]
    with connect(migrated_db_path) as connection:
        stored = connection.execute("SELECT password_hash FROM credentials").fetchone()[0]
        digest = connection.execute("SELECT token_hash FROM refresh_tokens").fetchone()[0]
    assert stored.startswith("$argon2id$") and verify_password(REGISTER["password"], stored)
    assert digest == hash_refresh_token(data["refreshToken"])
    assert stored not in response.text and digest not in response.text
    assert REGISTER["password"] not in response.text


async def test_login_and_independent_families(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    response = await auth_client.post(
        f"{AUTH}/login", json={"email": "PERSON@example.com", "password": REGISTER["password"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == original["user"]
    assert data["refreshToken"] != original["refreshToken"]
    with connect(migrated_db_path) as connection:
        assert connection.execute(
            "SELECT count(DISTINCT family_id) FROM refresh_tokens"
        ).fetchone() == (2,)


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": REGISTER["email"], "password": "wrong"},
        {"email": "missing@example.com", "password": REGISTER["password"]},
    ],
)
async def test_invalid_login_is_generic(
    auth_client: AsyncClient, credentials: dict[str, str]
) -> None:
    await register(auth_client)
    response = await auth_client.post(f"{AUTH}/login", json=credentials)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Could not validate credentials", "code": "unauthorized"}


async def test_duplicate_registration(auth_client: AsyncClient, migrated_db_path: Path) -> None:
    await register(auth_client)
    response = await auth_client.post(
        f"{AUTH}/register", json=REGISTER | {"email": " PERSON@EXAMPLE.COM "}
    )
    assert response.status_code == 409
    with connect(migrated_db_path) as connection:
        for table in ("users", "credentials", "refresh_tokens"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (1,)


@pytest.mark.parametrize(
    "override",
    [
        {"goal": None},
        {"goal": "unknown"},
        {"experienceLevel": "expert"},
        {"firstName": " "},
        {"lastName": "x" * 101},
        {"heightCm": 0},
        {"weightKg": -1},
        {"heightCm": 170.123},
        {"weightKg": "NaN"},
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "x" * 129},
        {"userId": str(uuid4())},
    ],
)
async def test_registration_validation(
    auth_client: AsyncClient, migrated_db_path: Path, override: dict[str, object]
) -> None:
    response = await auth_client.post(f"{AUTH}/register", json=REGISTER | override)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert REGISTER["password"] not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["errors"])
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone() == (0,)


async def test_missing_goal_and_form_login_rejected(auth_client: AsyncClient) -> None:
    payload = {key: value for key, value in REGISTER.items() if key != "goal"}
    response = await auth_client.post(f"{AUTH}/register", json=payload)
    assert response.status_code == 422
    response = await auth_client.post(
        f"{AUTH}/login", data={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert response.status_code == 422 and REGISTER["password"] not in response.text


@pytest.mark.parametrize(
    "header", [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic abc"}]
)
async def test_missing_or_invalid_access(auth_client: AsyncClient, header: dict[str, str]) -> None:
    response = await auth_client.get(ME, headers=header)
    assert response.status_code == 401


async def test_deleted_and_missing_users(
    auth_client: AsyncClient, migrated_db_path: Path, settings: Settings
) -> None:
    data = await register(auth_client)
    with connect(migrated_db_path) as connection:
        connection.execute("DELETE FROM users")
    assert (await auth_client.get(ME, headers=bearer(data))).status_code == 401
    for subject in (str(uuid4()), "not-a-uuid"):
        token = AccessTokens(settings).create(subject)
        assert (
            await auth_client.get(ME, headers={"Authorization": f"Bearer {token}"})
        ).status_code == 401


async def test_access_expiry_and_wrong_signature(
    auth_client: AsyncClient, settings: Settings
) -> None:
    user = (await register(auth_client))["user"]
    expired = jwt.encode(
        {
            "sub": user["id"],
            "iat": datetime.now(UTC) - timedelta(hours=1),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "type": "access",
        },
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )
    wrong = AccessTokens(settings.model_copy(update={"algorithm": "HS256"})).create(user["id"])
    wrong = wrong[:-8] + "AAAAAAAA"
    for token in (expired, wrong):
        assert (
            await auth_client.get(ME, headers={"Authorization": f"Bearer {token}"})
        ).status_code == 401


async def test_two_users_cannot_choose_identity(auth_client: AsyncClient) -> None:
    first = await register(auth_client)
    second = await register(auth_client, email="second@example.com")
    response = await auth_client.get(f"{ME}?userId={second['user']['id']}", headers=bearer(first))
    assert response.json() == first["user"]


def test_openapi_contract(auth_app: FastAPI) -> None:
    schema = auth_app.openapi()
    assert {f"{AUTH}/{name}" for name in ("register", "login", "refresh", "logout")} <= schema[
        "paths"
    ].keys()
    assert "password" not in schema["components"]["schemas"]["UserResponse"]["properties"]
    assert "goal" in schema["components"]["schemas"]["RegisterRequest"]["required"]
    assert schema["paths"][ME]["get"]["security"] == [{"HTTPBearer": []}]
