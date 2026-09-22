"""Token validation regressions and password round trips."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import AccessTokens, hash_password, verify_password


def test_access_token_round_trip(settings: Settings) -> None:
    tokens = AccessTokens(settings)
    token = tokens.create("user-123")
    assert tokens.decode(token) == "user-123"
    payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
    assert payload["exp"] - payload["iat"] == settings.access_token_expire_minutes * 60


@pytest.mark.parametrize("claim", ["sub", "iat", "exp", "type"])
def test_required_claims(settings: Settings, claim: str) -> None:
    payload = {
        "sub": "user",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=1),
        "type": "access",
    }
    del payload[claim]
    token = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")
    assert AccessTokens(settings).decode(token) is None


@pytest.mark.parametrize(
    "override",
    [
        {"exp": 1},
        {"sub": ""},
        {"sub": "   "},
        {"sub": 12},
        {"type": "refresh"},
        {"iat": 9999999999},
    ],
)
def test_invalid_claims(settings: Settings, override: dict[str, object]) -> None:
    payload = {
        "sub": "user",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=1),
        "type": "access",
    } | override
    token = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")
    assert AccessTokens(settings).decode(token) is None


def test_invalid_signature_algorithm_and_encoding(settings: Settings) -> None:
    tokens = AccessTokens(settings)
    valid = tokens.create("user")
    claims = jwt.decode(valid, settings.secret_key.get_secret_value(), algorithms=["HS256"])
    invalid = [
        "not-a-token",
        jwt.encode(claims, "a-different-signing-key-with-at-least-32-bytes", algorithm="HS256"),
        jwt.encode(claims, settings.secret_key.get_secret_value(), algorithm="HS384"),
        jwt.encode(claims, None, algorithm="none"),
    ]
    assert all(tokens.decode(token) is None for token in invalid)


def test_cannot_issue_empty_subject(settings: Settings) -> None:
    with pytest.raises(ValueError, match="subject"):
        AccessTokens(settings).create(" ")


def test_password_hash_round_trip() -> None:
    hashed = hash_password("test-password")
    assert hashed.startswith("$argon2id$")
    assert verify_password("test-password", hashed)
    assert not verify_password("wrong-password", hashed)
