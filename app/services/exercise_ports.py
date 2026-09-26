"""Catalog read ports keep SQLAlchemy out of use cases."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from app.core.enums import MuscleGroup
from app.schemas.exercise import ExerciseResponse


class ExerciseRepository(Protocol):
    async def list_exercises(
        self, group: MuscleGroup | None, limit: int, offset: int
    ) -> list[ExerciseResponse]: ...
    async def get(self, exercise_id: UUID) -> ExerciseResponse | None: ...


class ExerciseTransactions(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[ExerciseRepository]: ...
