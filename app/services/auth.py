"""Authentication use cases. No framework or database implementation dependencies."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.enums import RevocationReason
from app.core.exceptions import UnauthorizedError
from app.core.refresh_tokens import generate_refresh_token, hash_refresh_token
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_ports import (
    AccessTokenIssuer,
    AuthRepository,
    AuthTransactions,
    PasswordHasher,
    RefreshRecord,
)


class AuthService:
    def __init__(
        self,
        transactions: AuthTransactions,
        passwords: PasswordHasher,
        tokens: AccessTokenIssuer,
        access_lifetime_seconds: int,
        refresh_lifetime: timedelta,
    ) -> None:
        self._transactions = transactions
        self._passwords = passwords
        self._tokens = tokens
        self._access_lifetime_seconds = access_lifetime_seconds
        self._refresh_lifetime = refresh_lifetime

    async def _issue(
        self, repository: AuthRepository, user_id: UUID, family_id: UUID
    ) -> TokenResponse:
        raw = generate_refresh_token()
        now = datetime.now(UTC)
        await repository.add_refresh(
            user_id, family_id, hash_refresh_token(raw), now, now + self._refresh_lifetime
        )
        return TokenResponse(
            access_token=self._tokens.create(str(user_id)),
            refresh_token=raw,
            expires_in=self._access_lifetime_seconds,
        )

    async def register(self, data: RegisterRequest) -> AuthResponse:
        password_hash = await self._passwords.hash(data.password.get_secret_value())
        async with self._transactions.transaction(write=True) as repository:
            user = await repository.create_account(data, password_hash)
            tokens = await self._issue(repository, user.id, uuid4())
        return AuthResponse(**tokens.model_dump(), user=user)

    async def login(self, data: LoginRequest) -> AuthResponse:
        async with self._transactions.transaction() as repository:
            login = await repository.find_login(data.email)
        stored_hash = login.password_hash if login else None
        valid = await self._passwords.verify(data.password.get_secret_value(), stored_hash)
        if not valid or login is None:
            raise UnauthorizedError()
        async with self._transactions.transaction(write=True) as repository:
            current = await repository.find_login(data.email)
            if (
                current is None
                or current.password_hash != stored_hash
                or current.user.id != login.user.id
            ):
                raise UnauthorizedError()
            tokens = await self._issue(repository, current.user.id, uuid4())
        return AuthResponse(**tokens.model_dump(), user=current.user)

    async def _rotate(
        self, repository: AuthRepository, record: RefreshRecord
    ) -> TokenResponse | None:
        now = datetime.now(UTC)
        if record.revoked_at is not None:
            if record.revocation_reason == RevocationReason.ROTATED:
                await repository.revoke_family(
                    record.user_id, record.family_id, now, RevocationReason.REUSE
                )
            return None
        if record.expires_at <= now or await repository.get_user(record.user_id) is None:
            return None
        if not await repository.consume_refresh(record.id, now):
            return None
        return await self._issue(repository, record.user_id, record.family_id)

    async def refresh(self, raw: str) -> TokenResponse:
        async with self._transactions.transaction(write=True) as repository:
            record = await repository.find_refresh(hash_refresh_token(raw))
            tokens = await self._rotate(repository, record) if record else None
        # Raising outside the transaction preserves replay-triggered revocation.
        if tokens is None:
            raise UnauthorizedError()
        return tokens

    async def logout(self, raw: str) -> None:
        async with self._transactions.transaction(write=True) as repository:
            record = await repository.find_refresh(hash_refresh_token(raw))
            if record:
                await repository.revoke_family(
                    record.user_id, record.family_id, datetime.now(UTC), RevocationReason.LOGOUT
                )

    async def current_user(self, subject: str) -> UserResponse:
        try:
            user_id = UUID(subject)
        except ValueError:
            raise UnauthorizedError() from None
        async with self._transactions.transaction() as repository:
            user = await repository.get_user(user_id)
        if user is None:
            raise UnauthorizedError()
        return user
