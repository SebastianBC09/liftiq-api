"""Favorites integration: real migrations, transactional writes, and user isolation."""

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import AsyncClient

from alembic import command
from app.data.catalog import load_catalog
from app.repositories.favorites import SqlAlchemyFavoriteRepository
from scripts.seed_exercises import seed
from tests.auth_helpers import bearer, register
from tests.schema_helpers import connect

URL = "/api/v1/users/me/favorites"


@pytest.fixture
async def favorites(auth_app: FastAPI, auth_client: AsyncClient):
    await seed(auth_app.state.settings)
    headers = bearer(await register(auth_client))
    ids = [str(row.id) for row in load_catalog()[:3]]
    for exercise_id in ids:
        assert (await auth_client.put(f"{URL}/{exercise_id}", headers=headers)).status_code == 204
    return headers, ids


async def listed(client: AsyncClient, headers: dict[str, str]) -> list[str]:
    response = await client.get(URL, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    rows = response.json()
    assert [row["sortOrder"] for row in rows] == list(range(len(rows)))
    assert all(row["isFavorite"] for row in rows)
    return [row["id"] for row in rows]


async def test_idempotent_mutations_and_reseed(
    auth_client: AsyncClient, auth_app: FastAPI, favorites
):
    headers, ids = favorites
    assert await listed(auth_client, headers) == ids
    assert (await auth_client.put(f"{URL}/{ids[0]}", headers=headers)).status_code == 204
    await seed(auth_app.state.settings)
    assert await listed(auth_client, headers) == ids
    for _ in range(2):
        response = await auth_client.patch(
            URL + "/reorder", headers=headers, json={"exerciseIds": ids[::-1]}
        )
        assert response.status_code == 204 and response.content == b""
    assert await listed(auth_client, headers) == ids[::-1]
    for _ in range(2):
        assert (await auth_client.delete(f"{URL}/{ids[1]}", headers=headers)).status_code == 204
    assert await listed(auth_client, headers) == [ids[2], ids[0]]


async def test_user_isolation(auth_client: AsyncClient, favorites):
    first, ids = favorites
    second = bearer(await register(auth_client, email="second@example.com"))
    assert await listed(auth_client, second) == []
    await auth_client.put(f"{URL}/{ids[0]}", headers=second)
    assert await listed(auth_client, second) == [ids[0]]
    await auth_client.delete(f"{URL}/{ids[1]}", headers=second)
    response = await auth_client.patch(URL + "/reorder", headers=second, json={"exerciseIds": ids})
    assert response.status_code == 409
    assert await listed(auth_client, first) == ids
    assert await listed(auth_client, second) == [ids[0]]


@pytest.mark.parametrize("kind", ["missing", "extra", "duplicate", "malformed", "empty"])
async def test_invalid_reorder_is_atomic(auth_client: AsyncClient, favorites, kind: str):
    headers, ids = favorites
    orders = {
        "missing": ids[:1],
        "extra": [*ids, str(uuid4())],
        "duplicate": [ids[0]] * 3,
        "malformed": ["bad"],
        "empty": [],
    }
    response = await auth_client.patch(
        URL + "/reorder", headers=headers, json={"exerciseIds": orders[kind]}
    )
    assert response.status_code == (422 if kind in {"duplicate", "malformed"} else 409)
    assert await listed(auth_client, headers) == ids


async def test_missing_exercise_and_empty_reorder(auth_client: AsyncClient):
    headers = bearer(await register(auth_client))
    assert (await auth_client.put(f"{URL}/{uuid4()}", headers=headers)).status_code == 404
    assert (await auth_client.delete(f"{URL}/{uuid4()}", headers=headers)).status_code == 204
    assert (
        await auth_client.patch(URL + "/reorder", headers=headers, json={"exerciseIds": []})
    ).status_code == 204
    assert (await auth_client.put(URL + "/bad", headers=headers)).status_code == 422


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "", None),
        ("PUT", "/" + str(uuid4()), None),
        ("DELETE", "/" + str(uuid4()), None),
        ("PATCH", "/reorder", {"exerciseIds": []}),
    ],
)
async def test_requires_authentication(auth_client: AsyncClient, method, path, body):
    assert (await auth_client.request(method, URL + path, json=body)).status_code == 401


async def test_deleted_user_cannot_use_favorites(
    auth_client: AsyncClient, favorites, migrated_db_path: Path
):
    headers, _ = favorites
    with connect(migrated_db_path) as connection:
        connection.execute("DELETE FROM users")
        assert connection.execute("SELECT count(*) FROM user_favorites").fetchone() == (0,)
    assert (await auth_client.get(URL, headers=headers)).status_code == 401


async def test_concurrent_adds_and_reorders(auth_client: AsyncClient, favorites):
    headers, ids = favorites
    extra = str(load_catalog()[4].id)
    responses = await asyncio.gather(
        *[auth_client.put(f"{URL}/{extra}", headers=headers) for _ in range(4)]
    )
    assert all(response.status_code == 204 for response in responses)
    assert await listed(auth_client, headers) == [*ids, extra]
    orders = [[*ids, extra], [extra, *ids[::-1]]]
    responses = await asyncio.gather(
        *[
            auth_client.patch(URL + "/reorder", headers=headers, json={"exerciseIds": order})
            for order in orders
        ]
    )
    assert all(response.status_code == 204 for response in responses)
    assert await listed(auth_client, headers) in orders


async def test_reorder_failure_rolls_back(auth_client: AsyncClient, favorites):
    headers, ids = favorites
    original = SqlAlchemyFavoriteRepository.reorder

    async def fail(self, user_id: UUID, exercise_ids: list[UUID]):
        await original(self, user_id, exercise_ids)
        raise RuntimeError("injected failure")

    with patch.object(SqlAlchemyFavoriteRepository, "reorder", fail), pytest.raises(RuntimeError):
        await auth_client.patch(URL + "/reorder", headers=headers, json={"exerciseIds": ids[::-1]})
    assert await listed(auth_client, headers) == ids


async def test_database_constraints_and_cascades(favorites, migrated_db_path: Path):
    with connect(migrated_db_path) as connection:
        user, exercise, position = connection.execute(
            "SELECT * FROM user_favorites LIMIT 1"
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO user_favorites VALUES (?, ?, ?)", (user, exercise, position)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE user_favorites SET sort_order=-1 WHERE exercise_id=?", (exercise,)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE user_favorites SET sort_order=0 WHERE user_id=?", (user,))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO user_favorites VALUES (?, ?, ?)", (user, uuid4().hex, 9)
            )
        connection.execute("DELETE FROM exercises WHERE id=?", (exercise,))
        assert connection.execute("SELECT count(*) FROM user_favorites").fetchone() == (2,)


async def test_favorite_downgrade_preserves_catalog_and_auth(favorites, migrated_db_path: Path):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    await asyncio.to_thread(command.downgrade, config, "0002")
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM exercises").fetchone() == (35,)
        assert connection.execute("SELECT count(*) FROM users").fetchone() == (1,)
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.check, config)
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM user_favorites").fetchone() == (0,)
