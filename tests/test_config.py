"""Configuration failures must happen before requests or database writes."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "override",
    [
        {"secret_key": "short"},
        {"secret_key": "change-this-to-a-random-64-character-string"},
        {"algorithm": "none"},
        {"algorithm": "HS512"},
        {"access_token_expire_minutes": 0},
        {"refresh_token_expire_days": -1},
        {"database_url": "postgresql://localhost/db"},
        {"database_url": "sqlite+aiosqlite:///"},
        {"database_url": "not-a-url"},
        {"backend_cors_origins": ["*"]},
        {"backend_cors_origins": ["https://example.com/path"]},
        {"backend_cors_origins": ["https://example.com:99999"]},
        {"backend_cors_origins": ["https://user:password@example.com"]},
    ],
)
def test_invalid_settings(settings: Settings, override: dict[str, object]) -> None:
    values = settings.model_dump() | override
    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_secret_is_redacted(settings: Settings) -> None:
    assert settings.secret_key.get_secret_value() not in repr(settings)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, secret_key="sensitive-but-short")
    assert "sensitive-but-short" not in str(error.value)


def test_dotenv_can_be_disabled(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / ".env").write_text("SECRET_KEY=invalid\nDATABASE_URL=broken\n")
    monkeypatch.chdir(tmp_path)
    isolated = Settings(_env_file=None, **settings.model_dump())
    assert isolated.database_url == "sqlite+aiosqlite:///:memory:"
