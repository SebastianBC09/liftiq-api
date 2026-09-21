"""Validated runtime configuration; constructed only at application startup."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

MIN_SECRET_BYTES = 32


class Settings(BaseSettings):
    """Deployment settings. Tests disable dotenv loading with `_env_file=None`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True
    )

    database_url: str = "sqlite+aiosqlite:///./liftiq.db"
    secret_key: SecretStr
    algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)
    environment: Literal["development", "test", "production"] = "development"
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8100"])

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        """Reject short and example secrets without exposing them in errors."""
        secret = value.get_secret_value()
        if (
            len(secret.encode()) < MIN_SECRET_BYTES
            or not secret.strip()
            or secret.startswith("change-this")
        ):
            raise ValueError("SECRET_KEY must be a generated secret of at least 32 bytes")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """This deployment supports file-backed or in-memory async SQLite."""
        try:
            url = make_url(value)
        except ArgumentError as exc:
            raise ValueError("DATABASE_URL must be a valid async SQLite URL") from exc
        if (
            url.drivername != "sqlite+aiosqlite"
            or not url.database
            or url.host is not None
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or url.query
        ):
            raise ValueError(
                "DATABASE_URL must identify an async SQLite database without URL options"
            )
        return value

    @field_validator("backend_cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        """Require explicit origins rather than wildcards or full page URLs."""
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https", "capacitor", "ionic"}
                or not parsed.hostname
                or "*" in value
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS entries must be explicit origins without paths or credentials"
                )
            # Accessing port also validates its syntax and range.
            _ = parsed.port
        return values
