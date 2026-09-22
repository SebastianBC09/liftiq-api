"""Password hashing and access-token primitives; no implicit configuration."""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Hash a password with Argon2id; callers must offload this CPU-bound work."""
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password; callers must offload this CPU-bound work."""
    return password_hash.verify(plain_password, hashed_password)


class AccessTokens:
    """Issue and validate access tokens for one application's configuration."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, subject: str) -> str:
        """Issue a short-lived access token with a nonempty user identifier."""
        if not subject.strip():
            raise ValueError("Token subject must not be empty")
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": subject,
                "iat": now,
                "exp": now + timedelta(minutes=self._settings.access_token_expire_minutes),
                "type": "access",
            },
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

    def decode(self, token: str) -> str | None:
        """Return the subject only for a valid, unexpired access token."""
        try:
            payload = jwt.decode(
                token,
                self._settings.secret_key.get_secret_value(),
                algorithms=[self._settings.algorithm],
                options={"require": ["sub", "iat", "exp", "type"]},
            )
        except jwt.InvalidTokenError:
            return None
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject.strip() or payload["type"] != "access":
            return None
        return subject
