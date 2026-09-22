"""Raw database helpers shared by schema and migration integration tests."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

USER_SQL = """INSERT INTO users
(id, email, first_name, last_name, height_cm, weight_kg, experience_level, goal)
VALUES (:id, :email, :first_name, :last_name, :height_cm, :weight_kg, :experience_level, :goal)"""


@contextmanager
def connect(path: Path) -> Generator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def insert_user(connection: sqlite3.Connection, **overrides: object) -> str:
    values = {
        "id": uuid4().hex,
        "email": "user@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "height_cm": 170,
        "weight_kg": 65.25,
        "experience_level": "beginner",
        "goal": "technique",
    } | overrides
    connection.execute(USER_SQL, values)
    return str(values["id"])


def insert_token(connection: sqlite3.Connection, user_id: str, **overrides: object) -> None:
    values = {
        "id": uuid4().hex,
        "user_id": user_id,
        "family_id": uuid4().hex,
        "token_hash": "a" * 64,
        "issued_at": "2026-09-21 12:00:00.000000",
        "expires_at": "2026-10-21 12:00:00.000000",
        "revoked_at": None,
        "revocation_reason": None,
        "device_info": None,
    } | overrides
    connection.execute(
        """INSERT INTO refresh_tokens
        (id, user_id, family_id, token_hash, issued_at, expires_at,
         revoked_at, revocation_reason, device_info)
        VALUES (:id, :user_id, :family_id, :token_hash, :issued_at, :expires_at,
                :revoked_at, :revocation_reason, :device_info)""",
        values,
    )
