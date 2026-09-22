"""Check the migration runner now; domain revisions arrive in phase two."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import Settings


def test_migration_runner_is_independent_of_working_directory(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_KEY", settings.secret_key.get_secret_value())
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'migrations.db'}")
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    with sqlite3.connect(tmp_path / "migrations.db") as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert tables == [("alembic_version",)]


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
        "down_revision = None\n"
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
