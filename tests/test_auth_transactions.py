"""Atomic failures and concurrent requests use real, independent SQLite sessions."""

import asyncio
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import event

from app.core.passwords import Passwords
from app.core.security import AccessTokens
from tests.auth_helpers import AUTH, REGISTER, refresh, register
from tests.schema_helpers import connect


async def test_registration_rollback_on_token_failure(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    with (
        patch(
            "app.repositories.auth.SqlAlchemyAuthRepository.add_refresh",
            new_callable=AsyncMock,
            side_effect=RuntimeError("storage failure"),
        ),
        pytest.raises(RuntimeError, match="storage failure"),
    ):
        await auth_client.post(f"{AUTH}/register", json=REGISTER)
    with connect(migrated_db_path) as connection:
        for table in ("users", "credentials", "refresh_tokens"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


async def test_refresh_rollback_preserves_old_token(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    with (
        patch.object(AccessTokens, "create", side_effect=RuntimeError("signing failure")),
        pytest.raises(RuntimeError, match="signing failure"),
    ):
        await refresh(auth_client, original)
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM refresh_tokens").fetchone() == (1,)
        assert connection.execute("SELECT revoked_at FROM refresh_tokens").fetchone() == (None,)
    assert (await refresh(auth_client, original)).status_code == 200


async def test_concurrent_refresh_only_one_successor(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    results = await asyncio.gather(refresh(auth_client, original), refresh(auth_client, original))
    assert sorted(response.status_code for response in results) == [200, 401]
    winner = next(response.json() for response in results if response.status_code == 200)
    # The losing request triggers reuse detection and revokes the successor.
    assert (await refresh(auth_client, winner)).status_code == 401
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM refresh_tokens").fetchone() == (2,)
        assert connection.execute(
            "SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL"
        ).fetchone() == (0,)


async def test_concurrent_registration_is_atomic(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    results = await asyncio.gather(
        *(auth_client.post(f"{AUTH}/register", json=REGISTER) for _ in range(2))
    )
    assert sorted(response.status_code for response in results) == [201, 409]
    with connect(migrated_db_path) as connection:
        for table in ("users", "credentials", "refresh_tokens"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (1,)


async def test_concurrent_logout_and_refresh(
    auth_client: AsyncClient, migrated_db_path: Path
) -> None:
    original = await register(auth_client)
    rotated, logged_out = await asyncio.gather(
        refresh(auth_client, original),
        auth_client.post(f"{AUTH}/logout", json={"refreshToken": original["refreshToken"]}),
    )
    assert logged_out.status_code == 204 and rotated.status_code in (200, 401)
    if rotated.status_code == 200:
        assert (await refresh(auth_client, rotated.json())).status_code == 401
    with connect(migrated_db_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL"
        ).fetchone() == (0,)


async def test_login_rechecks_after_password_work(
    auth_client: AsyncClient, auth_app: FastAPI, migrated_db_path: Path
) -> None:
    await register(auth_client)
    original_verify = auth_app.state.passwords.verify

    async def delete_during_verification(password: str, stored_hash: str | None) -> bool:
        result = await original_verify(password, stored_hash)
        with connect(migrated_db_path) as connection:
            connection.execute("DELETE FROM users")
        return result

    with patch.object(auth_app.state.passwords, "verify", side_effect=delete_during_verification):
        response = await auth_client.post(
            f"{AUTH}/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
        )
    assert response.status_code == 401


async def test_unknown_user_still_verifies_a_hash(auth_client: AsyncClient) -> None:
    with patch("app.core.passwords.verify_password", return_value=True) as verify:
        response = await auth_client.post(
            f"{AUTH}/login", json={"email": "unknown@example.com", "password": "anything"}
        )
    assert response.status_code == 401
    verify.assert_called_once()
    assert verify.call_args.args[1].startswith("$argon2id$")


async def test_password_work_runs_off_event_loop() -> None:
    event_loop_thread = threading.get_ident()

    def assert_worker(*args: object) -> str:
        assert threading.get_ident() != event_loop_thread
        return "hash"

    with (
        patch("app.core.passwords.hash_password", side_effect=assert_worker),
        patch("app.core.passwords.verify_password", side_effect=assert_worker),
    ):
        passwords = await Passwords.create()
        await passwords.hash("password")
        assert await passwords.verify("password", "hash")


async def test_commit_failure_never_returns_tokens(
    auth_client: AsyncClient, auth_app: FastAPI, migrated_db_path: Path
) -> None:
    engine = auth_app.state.database.engine.sync_engine

    def fail_commit(connection: object) -> None:
        raise RuntimeError("commit failed")

    event.listen(engine, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="commit failed"):
            await auth_client.post(f"{AUTH}/register", json=REGISTER)
    finally:
        event.remove(engine, "commit", fail_commit)
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone() == (0,)
