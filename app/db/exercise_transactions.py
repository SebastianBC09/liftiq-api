"""Infrastructure adapter for read-only catalog transactions."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.db.session import Database
from app.repositories.exercises import SqlAlchemyExerciseRepository
from app.services.exercise_ports import ExerciseRepository


class SqlAlchemyExerciseTransactions:
    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[ExerciseRepository]:
        async with self._database.session() as session, session.begin():
            yield SqlAlchemyExerciseRepository(session)
