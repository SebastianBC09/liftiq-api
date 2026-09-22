"""Exercise real SQLite integrity and transactions without adding domain tables."""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import Database


async def test_foreign_keys_on_each_connection(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'integrity.db'}")
    try:
        async with database.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
            await connection.execute(
                text("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
            )
        async with database.engine.connect() as first, database.engine.connect() as second:
            for connection in (first, second):
                assert await connection.scalar(text("PRAGMA foreign_keys")) == 1
                with pytest.raises(IntegrityError):
                    await connection.execute(text("INSERT INTO child VALUES (999)"))
                await connection.rollback()
    finally:
        await database.dispose()


async def test_explicit_commit_and_rollback(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'transactions.db'}")
    try:
        async with database.engine.begin() as connection:
            await connection.execute(text("CREATE TABLE entry (id INTEGER PRIMARY KEY)"))
        async with database.session() as session, session.begin():
            await session.execute(text("INSERT INTO entry VALUES (1)"))
        async with database.session() as session:
            await session.execute(text("INSERT INTO entry VALUES (2)"))
        with pytest.raises(RuntimeError, match="abort"):
            async with database.session() as session, session.begin():
                await session.execute(text("INSERT INTO entry VALUES (3)"))
                raise RuntimeError("abort")
        async with database.session() as session:
            assert list((await session.scalars(text("SELECT id FROM entry"))).all()) == [1]
    finally:
        await database.dispose()


async def test_ddl_rolls_back(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'ddl.db'}")
    try:
        with pytest.raises(RuntimeError):
            async with database.engine.begin() as connection:
                await connection.execute(text("CREATE TABLE unfinished (id INTEGER)"))
                raise RuntimeError("abort migration")
        async with database.engine.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM sqlite_master WHERE name='unfinished'")
                )
                == 0
            )
    finally:
        await database.dispose()
