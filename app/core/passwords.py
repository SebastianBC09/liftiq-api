"""Async adapter for CPU-bound password work."""

import asyncio
import secrets

from app.core.security import hash_password, verify_password


class Passwords:
    def __init__(self, dummy_hash: str) -> None:
        self._dummy_hash = dummy_hash

    @classmethod
    async def create(cls) -> "Passwords":
        return cls(await asyncio.to_thread(hash_password, secrets.token_urlsafe(32)))

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(hash_password, password)

    async def verify(self, password: str, stored_hash: str | None) -> bool:
        matches = await asyncio.to_thread(
            verify_password, password, stored_hash or self._dummy_hash
        )
        return matches and stored_hash is not None
