"""Exercise database guarantees against migrations, including writes outside the ORM."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

from app.models import ExperienceLevel, RevocationReason, TrainingGoal
from tests.schema_helpers import connect, insert_token, insert_user


@pytest.mark.parametrize(
    "override",
    [
        {"email": " User@example.com "},
        {"email": "USER@example.com"},
        {"email": ""},
        {"first_name": " "},
        {"last_name": "x" * 101},
        {"height_cm": 0},
        {"weight_kg": -1},
        {"height_cm": "not-numeric"},
        {"weight_kg": 65.123},
        {"height_cm": float("inf")},
        {"experience_level": "expert"},
        {"goal": "unknown"},
        {"goal": None},
    ],
)
def test_user_constraints(migrated_db_path: Path, override: dict[str, object]) -> None:
    with connect(migrated_db_path) as connection, pytest.raises(sqlite3.IntegrityError):
        insert_user(connection, **override)


@pytest.mark.parametrize(
    "override",
    [
        {"token_hash": "raw-token"},
        {"token_hash": "g" * 64},
        {"family_id": None},
        {"expires_at": "2026-09-21 12:00:00.000000"},
        {"revoked_at": "2026-09-22 12:00:00.000000"},
        {"revocation_reason": "logout"},
        {"revoked_at": "2026-09-20 12:00:00.000000", "revocation_reason": "rotated"},
        {"revoked_at": "2026-09-22 12:00:00.000000", "revocation_reason": "unknown"},
        {"device_info": "x" * 513},
    ],
)
def test_token_constraints(migrated_db_path: Path, override: dict[str, object]) -> None:
    with connect(migrated_db_path) as connection:
        user_id = insert_user(connection)
        with pytest.raises(sqlite3.IntegrityError):
            insert_token(connection, user_id, **override)


def test_unique_credentials_and_token_hashes(migrated_db_path: Path) -> None:
    with connect(migrated_db_path) as connection:
        user_id = insert_user(connection)
        connection.execute(
            "INSERT INTO credentials (user_id, password_hash) VALUES (?, ?)", (user_id, "hash")
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO credentials (user_id, password_hash) VALUES (?, ?)",
                (user_id, "another-hash"),
            )
        insert_token(connection, user_id)
        with pytest.raises(sqlite3.IntegrityError):
            insert_token(connection, user_id)


def test_foreign_keys_and_cascade(migrated_db_path: Path) -> None:
    with connect(migrated_db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO credentials (user_id, password_hash) VALUES (?, ?)",
                (uuid4().hex, "hash"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            insert_token(connection, uuid4().hex)
        user_id = insert_user(connection)
        other_id = insert_user(connection, email="other@example.com")
        connection.execute(
            "INSERT INTO credentials (user_id, password_hash) VALUES (?, ?)", (user_id, "hash")
        )
        insert_token(connection, user_id)
        insert_token(connection, other_id, token_hash="b" * 64)
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        assert connection.execute("SELECT count(*) FROM credentials").fetchone() == (0,)
        assert connection.execute("SELECT user_id FROM refresh_tokens").fetchall() == [(other_id,)]


def test_registration_transaction_can_roll_back(migrated_db_path: Path) -> None:
    with pytest.raises(sqlite3.IntegrityError), connect(migrated_db_path) as connection:
        user_id = insert_user(connection)
        connection.execute(
            "INSERT INTO credentials (user_id, password_hash) VALUES (?, ?)", (user_id, "hash")
        )
        insert_token(connection, user_id, token_hash="invalid")
    with connect(migrated_db_path) as connection:
        for table in ("users", "credentials", "refresh_tokens"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_concurrent_duplicate_email_is_rejected(migrated_db_path: Path) -> None:
    barrier = Barrier(2)

    def register() -> bool:
        try:
            with connect(migrated_db_path) as connection:
                barrier.wait(timeout=5)
                insert_user(connection)
            return True
        except sqlite3.IntegrityError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: register(), range(2)))
    assert sorted(results) == [False, True]


def test_indexes_and_separation(migrated_db_path: Path) -> None:
    with connect(migrated_db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        assert "password_hash" not in columns and "password" not in columns
        token_columns = {row[1] for row in connection.execute("PRAGMA table_info(refresh_tokens)")}
        assert "token" not in token_columns and "refresh_token" not in token_columns
        index = connection.execute(
            "PRAGMA index_info(ix_refresh_tokens_user_id_family_id)"
        ).fetchall()
        assert [row[2] for row in index] == ["user_id", "family_id"]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("level", list(ExperienceLevel))
@pytest.mark.parametrize("goal", list(TrainingGoal))
def test_all_profile_enum_values(
    migrated_db_path: Path, level: ExperienceLevel, goal: TrainingGoal
) -> None:
    with connect(migrated_db_path) as connection:
        insert_user(connection, experience_level=level.value, goal=goal.value)


@pytest.mark.parametrize("reason", list(RevocationReason))
def test_valid_revocation_states(migrated_db_path: Path, reason: RevocationReason) -> None:
    with connect(migrated_db_path) as connection:
        user_id = insert_user(connection)
        insert_token(
            connection,
            user_id,
            revoked_at="2026-09-22 12:00:00.000000",
            revocation_reason=reason.value,
        )
