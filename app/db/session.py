"""SQLite connections and request-scoped sessions, owned by application lifespan."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _configure_sqlite(dbapi_connection: Any, connection_record: Any) -> None:
    """Enable integrity checks and let SQLAlchemy own transaction boundaries."""
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def _begin_sqlite(connection: Connection) -> None:
    """Make DDL and reads transactional too, instead of sqlite legacy behavior."""
    connection.exec_driver_sql("BEGIN")


class Database:
    """Own the engine and provide sessions without implicit commits."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, pool_pre_ping=True, hide_parameters=True)
        event.listen(self.engine.sync_engine, "connect", _configure_sqlite)
        event.listen(self.engine.sync_engine, "begin", _begin_sqlite)
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        """Use cases explicitly commit/begin; close rolls back any unfinished work."""
        async with self._sessions() as session:
            yield session

    async def dispose(self) -> None:
        """Release pooled connections at shutdown, including exceptional shutdown."""
        await self.engine.dispose()
