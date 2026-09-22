"""Current user's public profile."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthServiceDependency, get_current_user_id, prevent_caching
from app.schemas.auth import UserResponse
from app.schemas.errors import ErrorResponse

router = APIRouter(
    dependencies=[Depends(prevent_caching)], responses={401: {"model": ErrorResponse}}
)


@router.get("/me", response_model=UserResponse)
async def current_user(
    subject: Annotated[str, Depends(get_current_user_id)], service: AuthServiceDependency
) -> UserResponse:
    """Resolve a valid access token to an existing user without credential fields."""
    return await service.current_user(subject)
