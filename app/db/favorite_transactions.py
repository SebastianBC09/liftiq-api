"""Transaction adapter with serialized SQLite favorite writes."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.db.session import Database
from app.repositories.favorites import SqlAlchemyFavoriteRepository
from app.services.favorite_ports import FavoriteRepository


class SqlAlchemyFavoriteTransactions:
    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def transaction(self, *, write: bool = False) -> AsyncGenerator[FavoriteRepository]:
        async with self._database.session() as session, session.begin():
            if write:
                await session.connection(execution_options={"sqlite_write": True})
            yield SqlAlchemyFavoriteRepository(session)
