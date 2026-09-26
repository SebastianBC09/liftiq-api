"""User-isolated favorite operations, each owning one transaction."""

from uuid import UUID

from app.core.exceptions import ConflictError, EntityNotFoundError, UnauthorizedError
from app.schemas.favorite import FavoriteResponse
from app.services.favorite_ports import FavoriteRepository, FavoriteTransactions


async def require_user(repository: FavoriteRepository, user_id: UUID) -> None:
    if not await repository.user_exists(user_id):
        raise UnauthorizedError()


class FavoriteService:
    def __init__(self, transactions: FavoriteTransactions) -> None:
        self._transactions = transactions

    async def list_favorites(self, user_id: UUID) -> list[FavoriteResponse]:
        async with self._transactions.transaction() as repository:
            await require_user(repository, user_id)
            return await repository.list_favorites(user_id)

    async def add(self, user_id: UUID, exercise_id: UUID) -> None:
        async with self._transactions.transaction(write=True) as repository:
            await require_user(repository, user_id)
            if not await repository.exercise_exists(exercise_id):
                raise EntityNotFoundError("Exercise", str(exercise_id))
            await repository.add(user_id, exercise_id)

    async def remove(self, user_id: UUID, exercise_id: UUID) -> None:
        async with self._transactions.transaction(write=True) as repository:
            await require_user(repository, user_id)
            await repository.remove(user_id, exercise_id)

    async def reorder(self, user_id: UUID, exercise_ids: list[UUID]) -> None:
        async with self._transactions.transaction(write=True) as repository:
            await require_user(repository, user_id)
            current = await repository.ordered_ids(user_id)
            if len(exercise_ids) != len(set(exercise_ids)) or set(current) != set(exercise_ids):
                raise ConflictError("exerciseIds must contain every current favorite exactly once")
            await repository.reorder(user_id, exercise_ids)
