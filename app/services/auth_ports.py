"""Small persistence ports and snapshots for the authentication use cases."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.core.enums import RevocationReason
from app.schemas.auth import RegisterRequest, UserResponse


@dataclass(frozen=True)
class LoginRecord:
    user: UserResponse
    password_hash: str = field(repr=False)


@dataclass(frozen=True)
class RefreshRecord:
    id: UUID
    user_id: UUID
    family_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    revocation_reason: RevocationReason | None


class AuthRepository(Protocol):
    async def create_account(self, data: RegisterRequest, password_hash: str) -> UserResponse: ...
    async def find_login(self, email: str) -> LoginRecord | None: ...
    async def get_user(self, user_id: UUID) -> UserResponse | None: ...
    async def add_refresh(
        self, user_id: UUID, family_id: UUID, digest: str, issued_at: datetime, expires_at: datetime
    ) -> None: ...
    async def find_refresh(self, digest: str) -> RefreshRecord | None: ...
    async def consume_refresh(self, token_id: UUID, now: datetime) -> bool: ...
    async def revoke_family(
        self, user_id: UUID, family_id: UUID, now: datetime, reason: RevocationReason
    ) -> None: ...


class AuthTransactions(Protocol):
    def transaction(
        self, *, write: bool = False
    ) -> AbstractAsyncContextManager[AuthRepository]: ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...
    async def verify(self, password: str, stored_hash: str | None) -> bool: ...


class AccessTokenIssuer(Protocol):
    def create(self, subject: str) -> str: ...
