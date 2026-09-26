"""Catalog contracts, validated metadata, and atomic repeatable seeding."""

import asyncio
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError

from alembic import command
from app.core.config import Settings
from app.data.catalog import load_catalog
from app.repositories.exercises import SqlAlchemyExerciseRepository
from app.schemas.exercise import ExerciseContent, JointRange
from scripts.seed_exercises import seed
from tests.schema_helpers import connect, insert_user


async def test_catalog_seed_and_endpoints(
    auth_client: AsyncClient, auth_app: FastAPI, migrated_db_path: Path
) -> None:
    assert (await auth_client.get("/api/v1/exercises")).json() == []
    assert await seed(auth_app.state.settings) == 35
    with connect(migrated_db_path) as connection:
        ids = connection.execute("SELECT id FROM exercises ORDER BY id").fetchall()
    assert await seed(auth_app.state.settings) == 35
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT id FROM exercises ORDER BY id").fetchall() == ids
    response = await auth_client.get("/api/v1/exercises")
    assert response.status_code == 200
    exercises = response.json()
    assert len(exercises) == 35
    assert set(Counter(item["muscleGroup"] for item in exercises).values()) == {5}
    assert all(not item["analysisSupported"] for item in exercises)
    detail = await auth_client.get(f"/api/v1/exercises/{exercises[0]['id']}")
    assert detail.json() == exercises[0]
    filtered = await auth_client.get("/api/v1/exercises?muscle_group=chest")
    assert len(filtered.json()) == 5
    assert all(item["muscleGroup"] == "chest" for item in filtered.json())
    page = await auth_client.get("/api/v1/exercises?limit=2&offset=2")
    assert page.json() == exercises[2:4]


@pytest.mark.parametrize("query", ["muscle_group=invalid", "limit=0", "limit=101", "offset=-1"])
async def test_invalid_catalog_query(auth_client: AsyncClient, query: str) -> None:
    assert (await auth_client.get(f"/api/v1/exercises?{query}")).status_code == 422


async def test_missing_exercise(auth_client: AsyncClient) -> None:
    assert (await auth_client.get(f"/api/v1/exercises/{uuid4()}")).status_code == 404
    assert (await auth_client.get("/api/v1/exercises/not-a-uuid")).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"min": 100, "max": 20},
        {"ideal": 190},
        {"ideal": float("nan")},
        {"landmarks": ["left_shoulder", "left_elbow", "imaginary"]},
        {"landmarks": ["left_elbow", "left_elbow", "left_wrist"]},
    ],
)
def test_joint_range_validation(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JointRange.model_validate(
            {
                "min": 0,
                "max": 180,
                "ideal": 90,
                "landmarks": ["left_shoulder", "left_elbow", "left_wrist"],
            }
            | change
        )


def test_analysis_metadata_requires_complete_contract() -> None:
    content = load_catalog()[0].model_dump(exclude={"id"})
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(content | {"analysis_supported": True})
    angles = {
        "elbow": {
            "min": 10,
            "max": 160,
            "ideal": 90,
            "landmarks": ["left_shoulder", "left_elbow", "left_wrist"],
        }
    }
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(content | {"joint_angles": angles})
    valid = ExerciseContent.model_validate(
        content
        | {
            "analysis_supported": True,
            "joint_angles": angles,
            "analysis_version": 1,
            "camera_view": "side",
            "required_keypoints": ["left_shoulder", "left_elbow", "left_wrist"],
        }
    )
    assert valid.analysis_supported


async def test_seed_transaction_rollback(settings: Settings, migrated_db_path: Path) -> None:
    settings = settings.model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{migrated_db_path}"}
    )
    original = SqlAlchemyExerciseRepository.seed

    async def fail_after_writes(self: SqlAlchemyExerciseRepository, exercises):
        await original(self, exercises)
        raise RuntimeError("seed failed")

    with (
        patch.object(SqlAlchemyExerciseRepository, "seed", fail_after_writes),
        pytest.raises(RuntimeError),
    ):
        await seed(settings)
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM exercises").fetchone() == (0,)


def test_catalog_downgrade_preserves_accounts(settings: Settings, migrated_db_path: Path) -> None:
    configured = settings.model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{migrated_db_path}"}
    )
    asyncio.run(seed(configured))
    with connect(migrated_db_path) as connection:
        user_id = insert_user(connection)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "0001")
    with connect(migrated_db_path) as connection:
        assert connection.execute("SELECT id FROM users").fetchone() == (user_id,)
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE name='exercises'").fetchone()
            is None
        )
    command.upgrade(config, "head")
    command.check(config)
