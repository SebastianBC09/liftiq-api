"""Opaque refresh-token material; persistence only receives the SHA-256 digest."""

import hashlib
import secrets


def generate_refresh_token() -> str:
    """Generate 256 bits of randomness, encoded for safe transport."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Hash high-entropy token material for indexed lookup; not for passwords."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
