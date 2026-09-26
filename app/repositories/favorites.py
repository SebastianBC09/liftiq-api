"""SQL persistence; callers own transactions and serialize SQLite writers."""

from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise, User, UserFavorite
from app.schemas.exercise import ExerciseResponse
from app.schemas.favorite import FavoriteResponse


class SqlAlchemyFavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_exists(self, user_id: UUID) -> bool:
        return await self._session.get(User, user_id) is not None

    async def exercise_exists(self, exercise_id: UUID) -> bool:
        return await self._session.get(Exercise, exercise_id) is not None

    async def list_favorites(self, user_id: UUID) -> list[FavoriteResponse]:
        rows = await self._session.execute(
            select(Exercise, UserFavorite.sort_order)
            .join(UserFavorite, UserFavorite.exercise_id == Exercise.id)
            .where(UserFavorite.user_id == user_id)
            .order_by(UserFavorite.sort_order)
        )
        return [
            FavoriteResponse(
                **ExerciseResponse.model_validate(exercise).model_dump(), sort_order=order
            )
            for exercise, order in rows
        ]

    async def ordered_ids(self, user_id: UUID) -> list[UUID]:
        return list(
            await self._session.scalars(
                select(UserFavorite.exercise_id)
                .where(UserFavorite.user_id == user_id)
                .order_by(UserFavorite.sort_order)
            )
        )

    async def add(self, user_id: UUID, exercise_id: UUID) -> None:
        if await self._session.get(UserFavorite, (user_id, exercise_id)) is not None:
            return
        maximum = await self._session.scalar(
            select(func.max(UserFavorite.sort_order)).where(UserFavorite.user_id == user_id)
        )
        self._session.add(
            UserFavorite(
                user_id=user_id,
                exercise_id=exercise_id,
                sort_order=0 if maximum is None else maximum + 1,
            )
        )
        await self._session.flush()

    async def remove(self, user_id: UUID, exercise_id: UUID) -> None:
        await self._session.execute(
            delete(UserFavorite).where(
                UserFavorite.user_id == user_id, UserFavorite.exercise_id == exercise_id
            )
        )
        await self.reorder(user_id, await self.ordered_ids(user_id))

    async def reorder(self, user_id: UUID, exercise_ids: list[UUID]) -> None:
        if not exercise_ids:
            return
        maximum = await self._session.scalar(
            select(func.max(UserFavorite.sort_order)).where(UserFavorite.user_id == user_id)
        )
        # Move every position above the occupied range before assigning the new order.
        # This preserves the immediate unique constraint even when swapping neighbors.
        offset = (maximum or 0) + 1
        await self._session.execute(
            update(UserFavorite)
            .where(UserFavorite.user_id == user_id)
            .values(sort_order=UserFavorite.sort_order + offset)
        )
        for position, exercise_id in enumerate(exercise_ids):
            await self._session.execute(
                update(UserFavorite)
                .where(UserFavorite.user_id == user_id, UserFavorite.exercise_id == exercise_id)
                .values(sort_order=position)
            )
