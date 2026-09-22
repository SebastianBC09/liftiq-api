"""Thin JSON auth endpoints; use cases own persistence and token behavior."""

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthServiceDependency, prevent_caching
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.errors import ErrorResponse, ValidationErrorResponse

router = APIRouter(
    dependencies=[Depends(prevent_caching)],
    responses={401: {"model": ErrorResponse}, 422: {"model": ValidationErrorResponse}},
)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
async def register(data: RegisterRequest, service: AuthServiceDependency) -> AuthResponse:
    """Create a user, credentials, and refresh family in one transaction."""
    return await service.register(data)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, service: AuthServiceDependency) -> AuthResponse:
    """Authenticate by email/password and create an independent login family."""
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, service: AuthServiceDependency) -> TokenResponse:
    """Rotate once. Reusing a consumed token revokes its family's active tokens."""
    return await service.refresh(data.refresh_token.get_secret_value())


@router.post("/logout", status_code=204)
async def logout(data: RefreshRequest, service: AuthServiceDependency) -> None:
    """Revoke this token's family. Unknown/repeated tokens also return 204."""
    await service.logout(data.refresh_token.get_secret_value())
