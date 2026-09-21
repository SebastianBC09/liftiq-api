"""HTTP dependency wiring; business services do not import this module."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.security import AccessTokens
from app.db.session import Database

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
    """Validate the bearer subject; user existence will be checked in phase three."""
    if credentials is None:
        raise UnauthorizedError()
    subject = AccessTokens(settings).decode(credentials.credentials)
    if subject is None:
        raise UnauthorizedError()
    return subject
