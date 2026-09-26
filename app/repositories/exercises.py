"""Catalog querying and validated idempotent seeding."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MuscleGroup
from app.models.exercise import Exercise
from app.schemas.exercise import ExerciseResponse


class SqlAlchemyExerciseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_exercises(
        self, group: MuscleGroup | None, limit: int, offset: int
    ) -> list[ExerciseResponse]:
        statement = (
            select(Exercise).order_by(Exercise.name, Exercise.id).limit(limit).offset(offset)
        )
        if group is not None:
            statement = statement.where(Exercise.muscle_group == group.value)
        exercises = await self._session.scalars(statement)
        return [ExerciseResponse.model_validate(exercise) for exercise in exercises]

    async def get(self, exercise_id: UUID) -> ExerciseResponse | None:
        exercise = await self._session.get(Exercise, exercise_id)
        return ExerciseResponse.model_validate(exercise) if exercise else None

    async def seed(self, exercises: list[ExerciseResponse]) -> None:
        """Update known seed rows without deleting other catalog data or changing IDs."""
        for exercise in exercises:
            values = exercise.model_dump(mode="json", exclude={"id"}) | {"id": exercise.id}
            statement = insert(Exercise).values(**values)
            updates = {key: getattr(statement.excluded, key) for key in values if key != "id"}
            await self._session.execute(
                statement.on_conflict_do_update(index_elements=["id"], set_=updates)
            )
