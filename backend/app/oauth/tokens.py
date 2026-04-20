"""OAuth token issuance + verification + revocation blacklist.

Access tokens are JWTs (HS256). Refresh tokens are opaque 67-char strings
("rt_" + 64 random hex chars from token_hex(32)), stored as sha256 hashes.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.ulid import new_ulid

_ISSUER = "https://vibecell.dev"
_AUDIENCE = "https://vibecell.dev/mcp"


@dataclass(frozen=True, slots=True)
class OAuthTokenClaims:
    sub: str
    client_id: str
    workspace_id: str
    scope: str
    jti: str | None = None
    iat: int = 0
    exp: int = 0


def issue_access_token(claims: OAuthTokenClaims) -> tuple[str, str]:
    """Return (jwt_string, jti). jti is the ULID used for revocation lookup."""
    s = get_settings()
    jti = new_ulid()
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": claims.sub,
        "client_id": claims.client_id,
        "workspace_id": claims.workspace_id,
        "scope": claims.scope,
        "iat": now,
        "exp": now + s.oauth_access_token_ttl_seconds,
        "jti": jti,
    }
    encoded = jwt.encode(payload, s.oauth_jwt_secret, algorithm="HS256")
    return encoded, jti


def verify_access_token(token: str) -> OAuthTokenClaims:
    s = get_settings()
    try:
        payload = jwt.decode(
            token, s.oauth_jwt_secret, algorithms=["HS256"],
            audience=_AUDIENCE, issuer=_ISSUER,
            options={"require": ["iss", "aud", "sub", "exp", "iat", "jti", "client_id", "workspace_id", "scope"]},
            leeway=30,  # fix I-3 — 30s clock-skew tolerance
        )
    except jwt.PyJWTError as e:
        raise ValueError("invalid_token") from e
    return OAuthTokenClaims(
        sub=payload["sub"],
        client_id=payload["client_id"],
        workspace_id=payload["workspace_id"],
        scope=payload["scope"],
        jti=payload["jti"],
        iat=payload["iat"],
        exp=payload["exp"],
    )


_REFRESH_PREFIX = "rt_"


def issue_refresh_token() -> str:
    return _REFRESH_PREFIX + secrets.token_hex(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class JTIBlacklist:
    """Redis-backed set of revoked JTIs. Keys auto-expire at the token's exp."""

    _PREFIX = "oauth:revoked_jti:"

    async def add(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            # Token is already expired — revocation would expire instantly. No-op is safe.
            return
        r = await get_redis()
        await r.set(f"{self._PREFIX}{jti}", "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        r = await get_redis()
        return bool(await r.exists(f"{self._PREFIX}{jti}"))
