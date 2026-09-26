"""Public exercise catalog endpoints."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.core.enums import MuscleGroup
from app.db.exercise_transactions import SqlAlchemyExerciseTransactions
from app.db.session import Database
from app.schemas.errors import ErrorResponse, ValidationErrorResponse
from app.schemas.exercise import ExerciseResponse
from app.services.exercises import ExerciseService

router = APIRouter(responses={422: {"model": ValidationErrorResponse}})


def get_service(request: Request) -> ExerciseService:
    return ExerciseService(
        SqlAlchemyExerciseTransactions(cast(Database, request.app.state.database))
    )


Service = Annotated[ExerciseService, Depends(get_service)]


@router.get("", response_model=list[ExerciseResponse])
async def list_exercises(
    service: Service,
    muscle_group: MuscleGroup | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ExerciseResponse]:
    return await service.list_exercises(muscle_group, limit, offset)


@router.get(
    "/{exercise_id}", response_model=ExerciseResponse, responses={404: {"model": ErrorResponse}}
)
async def get_exercise(exercise_id: UUID, service: Service) -> ExerciseResponse:
    return await service.get(exercise_id)
