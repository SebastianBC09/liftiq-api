"""HTTP dependency wiring; business services do not import this module."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated, cast

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.passwords import Passwords
from app.core.security import AccessTokens
from app.db.auth_transactions import SqlAlchemyAuthTransactions
from app.db.session import Database
from app.services.auth import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    """Resolve configuration from this application, not a process-global cache."""
    return cast(Settings, request.app.state.settings)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one session per request; the use case owns its transaction."""
    database = cast(Database, request.app.state.database)
    async with database.session() as session:
        yield session


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Validate the bearer subject; the current-user use case also checks existence."""
    if credentials is None:
        raise UnauthorizedError()
    subject = AccessTokens(settings).decode(credentials.credentials)
    if subject is None:
        raise UnauthorizedError()
    return subject


def get_auth_service(request: Request) -> AuthService:
    """Wire infrastructure into the framework-independent auth use cases."""
    settings = get_settings(request)
    return AuthService(
        SqlAlchemyAuthTransactions(cast(Database, request.app.state.database)),
        cast(Passwords, request.app.state.passwords),
        AccessTokens(settings),
        settings.access_token_expire_minutes * 60,
        timedelta(days=settings.refresh_token_expire_days),
    )


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


def prevent_caching(response: Response) -> None:
    """Auth and profile responses must not be stored by HTTP caches."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
