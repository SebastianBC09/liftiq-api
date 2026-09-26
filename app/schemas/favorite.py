"""Favorite HTTP contracts."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import ApiModel
from app.schemas.exercise import ExerciseResponse


class FavoriteResponse(ExerciseResponse):
    is_favorite: Literal[True] = True
    sort_order: int = Field(ge=0)


class ReorderFavorites(ApiModel):
    exercise_ids: list[UUID]

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len(self.exercise_ids) != len(set(self.exercise_ids)):
            raise ValueError("exerciseIds must not contain duplicates")
        return self
