import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HANGAR_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("HANGAR_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("HANGAR_MASTER_KEY", "x" * 43)  # 32 bytes base64url = 43 chars
    monkeypatch.setenv("HANGAR_RESEND_API_KEY", "re_test")
    monkeypatch.setenv("HANGAR_GITHUB_CLIENT_ID", "gh_client")
    monkeypatch.setenv("HANGAR_GITHUB_CLIENT_SECRET", "gh_secret")
    monkeypatch.setenv("HANGAR_BASE_URL", "http://localhost:3000")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.master_key == "x" * 43
    assert settings.base_url == "http://localhost:3000"
    assert settings.cookie_domain == "localhost"  # default
    assert settings.session_max_age == 2592000  # default
    assert settings.dev_mode is False  # default


def test_settings_rejects_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ["HANGAR_DATABASE_URL", "HANGAR_MASTER_KEY", "HANGAR_REDIS_URL",
                "HANGAR_RESEND_API_KEY", "HANGAR_GITHUB_CLIENT_ID",
                "HANGAR_GITHUB_CLIENT_SECRET", "HANGAR_BASE_URL"]:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValidationError):
        Settings()
