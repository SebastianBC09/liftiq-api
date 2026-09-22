"""Rotation, family isolation, logout, and expiry through HTTP."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.refresh_tokens import hash_refresh_token
from tests.auth_helpers import AUTH, ME, REGISTER, bearer, refresh, register
from tests.schema_helpers import connect


async def test_rotation_and_reuse_commit_revocation(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    response = await refresh(auth_client, original)
    assert response.status_code == 200
    successor = response.json()
    assert set(successor) == {"accessToken", "refreshToken", "tokenType", "expiresIn"}
    assert successor["refreshToken"] != original["refreshToken"]
    with connect(migrated_db_path) as connection:
        assert connection.execute(
            "SELECT count(DISTINCT family_id) FROM refresh_tokens"
        ).fetchone() == (1,)
    assert (await refresh(auth_client, original)).status_code == 401
    assert (await refresh(auth_client, successor)).status_code == 401
    with connect(migrated_db_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL"
        ).fetchone() == (0,)
        reasons = {
            row[0] for row in connection.execute("SELECT revocation_reason FROM refresh_tokens")
        }
        assert reasons == {"rotated", "reuse"}


async def test_reuse_does_not_revoke_other_logins_or_users(auth_client: AsyncClient) -> None:
    original = await register(auth_client)
    other_user = await register(auth_client, email="other@example.com")
    login = await auth_client.post(
        f"{AUTH}/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert (await refresh(auth_client, original)).status_code == 200
    assert (await refresh(auth_client, original)).status_code == 401
    assert (await refresh(auth_client, login.json())).status_code == 200
    assert (await refresh(auth_client, other_user)).status_code == 200


async def test_logout_with_ancestor_revokes_successor(auth_client: AsyncClient) -> None:
    original = await register(auth_client)
    successor = (await refresh(auth_client, original)).json()
    for _ in range(2):
        response = await auth_client.post(
            f"{AUTH}/logout", json={"refreshToken": original["refreshToken"]}
        )
        assert response.status_code == 204 and response.content == b""
    assert (await refresh(auth_client, successor)).status_code == 401
    assert (await auth_client.get(ME, headers=bearer(original))).status_code == 200


async def test_expired_refresh_and_unknown_logout(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    with connect(migrated_db_path) as connection:
        connection.execute(
            "UPDATE refresh_tokens SET issued_at='2000-01-01 00:00:00.000000', "
            "expires_at='2000-01-02 00:00:00.000000'"
        )
    assert (await refresh(auth_client, original)).status_code == 401
    assert (
        await auth_client.post(f"{AUTH}/logout", json={"refreshToken": "unknown"})
    ).status_code == 204


async def test_deleted_user_cannot_refresh(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    with connect(migrated_db_path) as connection:
        connection.execute("DELETE FROM users")
    assert (await refresh(auth_client, original)).status_code == 401


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"refreshToken": "unknown"}, 401),
        ({}, 422),
        ({"refreshToken": ""}, 422),
        ({"refreshToken": "x" * 513}, 422),
        ({"refreshToken": None}, 422),
    ],
)
async def test_invalid_refresh_input(
    auth_client: AsyncClient, payload: dict[str, object], status: int
) -> None:
    response = await auth_client.post(f"{AUTH}/refresh", json=payload)
    assert response.status_code == status


async def test_raw_tokens_are_not_persisted(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    successor = (await refresh(auth_client, original)).json()
    with connect(migrated_db_path) as connection:
        dump = "\n".join(connection.iterdump())
    for data in (original, successor):
        assert data["refreshToken"] not in dump
        assert data["accessToken"] not in dump
        assert hash_refresh_token(data["refreshToken"]) in dump


async def test_logout_scopes_family_to_user(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    first = await register(auth_client)
    other = await register(auth_client, email="other@example.com")
    # Family identifiers are scoped by user, even if persisted values collide.
    with connect(migrated_db_path) as connection:
        connection.execute("UPDATE refresh_tokens SET family_id = ?", ("a" * 32,))
    response = await auth_client.post(
        f"{AUTH}/logout", json={"refreshToken": first["refreshToken"]}
    )
    assert response.status_code == 204
    assert (await refresh(auth_client, first)).status_code == 401
    assert (await refresh(auth_client, other)).status_code == 200
