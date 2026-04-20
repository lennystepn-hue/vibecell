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

    # OAuth 2.1 — Remote MCP Server (Spec 3.5)
    oauth_jwt_secret: str = Field(
        description="Legacy HS256 signing secret (unused after RS256 migration). Kept to avoid breaking existing .env files.",
        default="",
    )
    oauth_private_key_b64: str = Field(
        description="RSA private key (PEM, base64-encoded) for signing OAuth JWTs",
        default="",
    )
    oauth_public_key_b64: str = Field(
        description="RSA public key (PEM, base64-encoded)",
        default="",
    )
    oauth_jwt_kid: str = Field(
        description="Key id published in JWKS + JWT header",
        default="vibecell-k1",
    )
    oauth_access_token_ttl_seconds: int = 3600        # 1 hour
    oauth_refresh_token_ttl_seconds: int = 30 * 86400 # 30 days
    oauth_auth_code_ttl_seconds: int = 60
    oauth_max_clients_per_user: int = 50
    oauth_dcr_orphan_ttl_hours: int = 24


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
