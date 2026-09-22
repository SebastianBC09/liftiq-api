"""Persistence for the auth aggregate. Transaction ownership belongs to the caller."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RevocationReason
from app.models import Credential, RefreshToken, User
from app.schemas.auth import RegisterRequest, UserResponse
from app.services.auth_ports import LoginRecord, RefreshRecord


class SqlAlchemyAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_account(self, data: RegisterRequest, password_hash: str) -> UserResponse:
        user = User(**data.model_dump(exclude={"password"}))
        self._session.add(user)
        await self._session.flush()
        self._session.add(Credential(user_id=user.id, password_hash=password_hash))
        await self._session.flush()
        return UserResponse.model_validate(user)

    async def find_login(self, email: str) -> LoginRecord | None:
        result = await self._session.execute(
            select(User, Credential.password_hash).join(Credential).where(User.email == email)
        )
        row = result.one_or_none()
        return LoginRecord(UserResponse.model_validate(row[0]), row[1]) if row else None

    async def get_user(self, user_id: UUID) -> UserResponse | None:
        user = await self._session.get(User, user_id)
        return UserResponse.model_validate(user) if user else None

    async def add_refresh(
        self, user_id: UUID, family_id: UUID, digest: str, issued_at: datetime, expires_at: datetime
    ) -> None:
        self._session.add(
            RefreshToken(
                user_id=user_id,
                family_id=family_id,
                token_hash=digest,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        )
        await self._session.flush()

    async def find_refresh(self, digest: str) -> RefreshRecord | None:
        token = await self._session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == digest)
        )
        if token is None:
            return None
        return RefreshRecord(
            token.id,
            token.user_id,
            token.family_id,
            token.expires_at,
            token.revoked_at,
            token.revocation_reason,
        )

    async def consume_refresh(self, token_id: UUID, now: datetime) -> bool:
        """Consume once with a conditional write, even if the caller raced another request."""
        result = await self._session.scalar(
            update(RefreshToken)
            .where(
                RefreshToken.id == token_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .values(revoked_at=now, revocation_reason=RevocationReason.ROTATED)
            .returning(RefreshToken.id)
        )
        return result is not None

    async def revoke_family(
        self, user_id: UUID, family_id: UUID, now: datetime, reason: RevocationReason
    ) -> None:
        """Keep consumed ancestors for reuse detection; revoke every live successor."""
        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now, revocation_reason=reason)
        )
