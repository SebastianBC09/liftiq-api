"""Verify the real auth migration, schema drift, and failure rollback."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import Settings
from tests.schema_helpers import connect, insert_token, insert_user


def test_migration_runner_is_independent_of_working_directory(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_KEY", settings.secret_key.get_secret_value())
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'migrations.db'}")
    command.upgrade(config, "head")
    command.check(config)
    with connect(tmp_path / "migrations.db") as connection:
        user_id = insert_user(connection)
        connection.execute(
            "INSERT INTO credentials (user_id, password_hash) VALUES (?, ?)", (user_id, "hash")
        )
        insert_token(connection, user_id)
    command.downgrade(config, "base")
    with connect(tmp_path / "migrations.db") as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall() == [("alembic_version",)]
    command.upgrade(config, "head")
    with sqlite3.connect(tmp_path / "migrations.db") as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert {name for (name,) in tables} == {
        "alembic_version",
        "users",
        "credentials",
        "refresh_tokens",
        "exercises",
        "user_favorites",
    }


def test_failed_migration_rolls_back_ddl(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A temporary test revision proves Alembic uses the transactional connection."""
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "alembic", tmp_path / "alembic")
    shutil.copyfile(root / "alembic.ini", tmp_path / "alembic.ini")
    (tmp_path / "alembic/versions/test_failure.py").write_text(
        "from alembic import op\n"
        'revision = "test_failure"\n'
        'down_revision = "0003"\n'
        "def upgrade():\n"
        '    op.execute("CREATE TABLE incomplete (id INTEGER)")\n'
        '    raise RuntimeError("intentional migration failure")\n'
        "def downgrade():\n"
        "    pass\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_KEY", settings.secret_key.get_secret_value())
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'failure.db'}")
    with pytest.raises(RuntimeError, match="intentional migration failure"):
        command.upgrade(Config(str(tmp_path / "alembic.ini")), "head")
    with sqlite3.connect(tmp_path / "failure.db") as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert tables == []
