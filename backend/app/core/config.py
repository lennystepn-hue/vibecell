from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HANGAR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(..., description="postgresql+asyncpg://... (no default)")
    redis_url: str = Field(..., description="redis://host:port/db")
    master_key: str = Field(..., min_length=32, description="base64url-encoded 32-byte key for AES-256-GCM")
    resend_api_key: str = Field(...)
    github_client_id: str = Field(...)
    github_client_secret: str = Field(...)
    base_url: str = Field(..., description="public root URL (for magic-link emails, OAuth redirects)")
    cookie_domain: str = Field(default="localhost")
    session_max_age: int = Field(default=2592000, description="session cookie TTL in seconds (default 30 days)")
    sentry_dsn: str = Field(default="")
    dev_mode: bool = Field(default=False, description="when true, magic links print to log instead of email")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
