"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from the environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+aiosqlite:///./liftiq.db"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    environment: str = "development"
    backend_cors_origins: list[str] = ["http://localhost:8100"]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so env parsing happens once per process."""
    return Settings()
