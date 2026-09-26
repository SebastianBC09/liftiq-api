"""Authenticated favorites routes; ordering and membership belong to the service."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_current_user_id, prevent_caching
from app.core.exceptions import UnauthorizedError
from app.db.favorite_transactions import SqlAlchemyFavoriteTransactions
from app.db.session import Database
from app.schemas.errors import ErrorResponse, ValidationErrorResponse
from app.schemas.favorite import FavoriteResponse, ReorderFavorites
from app.services.favorites import FavoriteService

router = APIRouter(
    dependencies=[Depends(prevent_caching)],
    responses={401: {"model": ErrorResponse}, 422: {"model": ValidationErrorResponse}},
)


def get_service(request: Request) -> FavoriteService:
    return FavoriteService(
        SqlAlchemyFavoriteTransactions(cast(Database, request.app.state.database))
    )


async def user_id(subject: Annotated[str, Depends(get_current_user_id)]) -> UUID:
    try:
        return UUID(subject)
    except ValueError as error:
        raise UnauthorizedError() from error


Service = Annotated[FavoriteService, Depends(get_service)]
CurrentUser = Annotated[UUID, Depends(user_id)]


@router.get("", response_model=list[FavoriteResponse])
async def list_favorites(user: CurrentUser, service: Service) -> list[FavoriteResponse]:
    return await service.list_favorites(user)


@router.patch("/reorder", status_code=204, responses={409: {"model": ErrorResponse}})
async def reorder(body: ReorderFavorites, user: CurrentUser, service: Service) -> None:
    await service.reorder(user, body.exercise_ids)


@router.put("/{exercise_id}", status_code=204, responses={404: {"model": ErrorResponse}})
async def add(exercise_id: UUID, user: CurrentUser, service: Service) -> None:
    await service.add(user, exercise_id)


@router.delete("/{exercise_id}", status_code=204)
async def remove(exercise_id: UUID, user: CurrentUser, service: Service) -> None:
    await service.remove(user, exercise_id)
