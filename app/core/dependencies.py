"""Shared FastAPI dependencies: DB session and current-user resolution."""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Yield a request-scoped async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """Resolve the authenticated user id (JWT subject) from the bearer token.

    NOTE: once the User model/repository exist, add a `get_current_user()`
    dependency on top of this that fetches the full User row.
    """
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
