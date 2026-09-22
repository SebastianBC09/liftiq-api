"""Unit-of-work adapter for SQLite auth transactions."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError
from app.db.session import Database
from app.repositories.auth import SqlAlchemyAuthRepository
from app.services.auth_ports import AuthRepository


class SqlAlchemyAuthTransactions:
    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def transaction(self, *, write: bool = False) -> AsyncGenerator[AuthRepository]:
        """Commit once; rollback on failure. Acquire SQLite's write lock before reads."""
        try:
            async with self._database.session() as session, session.begin():
                if write:
                    await session.connection(execution_options={"sqlite_write": True})
                yield SqlAlchemyAuthRepository(session)
        except IntegrityError as exc:
            if str(exc.orig) == "UNIQUE constraint failed: users.email":
                raise ConflictError("Email is already registered") from None
            raise
