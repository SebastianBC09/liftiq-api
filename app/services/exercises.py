"""Read-only catalog use cases."""

from uuid import UUID

from app.core.enums import MuscleGroup
from app.core.exceptions import EntityNotFoundError
from app.schemas.exercise import ExerciseResponse
from app.services.exercise_ports import ExerciseTransactions


class ExerciseService:
    def __init__(self, transactions: ExerciseTransactions) -> None:
        self._transactions = transactions

    async def list_exercises(
        self, group: MuscleGroup | None, limit: int, offset: int
    ) -> list[ExerciseResponse]:
        async with self._transactions.transaction() as repository:
            return await repository.list_exercises(group, limit, offset)

    async def get(self, exercise_id: UUID) -> ExerciseResponse:
        async with self._transactions.transaction() as repository:
            exercise = await repository.get(exercise_id)
        if exercise is None:
            raise EntityNotFoundError("Exercise", str(exercise_id))
        return exercise
