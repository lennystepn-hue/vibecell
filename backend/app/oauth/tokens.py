"""OAuth token issuance + verification + revocation blacklist.

Access tokens are JWTs (RS256). Refresh tokens are opaque 67-char strings
("rt_" + 64 random hex chars from token_hex(32)), stored as sha256 hashes.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.ulid import new_ulid

_ISSUER = "https://vibecell.dev"
_DEFAULT_AUDIENCE = "https://vibecell.dev"  # base URL — matches what users enter in clients
_ACCEPTED_AUDIENCES = {"https://vibecell.dev", "https://vibecell.dev/mcp"}


@dataclass(frozen=True, slots=True)
class OAuthTokenClaims:
    sub: str
    client_id: str
    workspace_id: str
    scope: str
    audience: str | None = None  # Override default aud (from RFC 8707 resource param)
    jti: str | None = None
    iat: int = 0
    exp: int = 0


def _load_private_key() -> bytes:
    s = get_settings()
    if not s.oauth_private_key_b64:
        raise RuntimeError("HANGAR_OAUTH_PRIVATE_KEY_B64 is not set")
    return base64.b64decode(s.oauth_private_key_b64)


def _load_public_key() -> bytes:
    s = get_settings()
    if not s.oauth_public_key_b64:
        raise RuntimeError("HANGAR_OAUTH_PUBLIC_KEY_B64 is not set")
    return base64.b64decode(s.oauth_public_key_b64)


def issue_access_token(claims: OAuthTokenClaims) -> tuple[str, str]:
    """Return (jwt_string, jti). jti is the ULID used for revocation lookup."""
    s = get_settings()
    jti = new_ulid()
    now = int(datetime.now(UTC).timestamp())
    aud = claims.audience or _DEFAULT_AUDIENCE
    payload = {
        "iss": _ISSUER,
        "aud": aud,
        "sub": claims.sub,
        "client_id": claims.client_id,
        "workspace_id": claims.workspace_id,
        "scope": claims.scope,
        "iat": now,
        "exp": now + s.oauth_access_token_ttl_seconds,
        "jti": jti,
    }
    encoded = jwt.encode(
        payload,
        _load_private_key(),
        algorithm="RS256",
        headers={"kid": s.oauth_jwt_kid, "typ": "at+jwt"},
    )
    return encoded, jti


def verify_access_token(token: str) -> OAuthTokenClaims:
    """Verify an access token. Accepts either canonical audience value."""
    try:
        payload = jwt.decode(
            token,
            _load_public_key(),
            algorithms=["RS256"],
            audience=list(_ACCEPTED_AUDIENCES),
            issuer=_ISSUER,
            options={"require": ["iss", "aud", "sub", "exp", "iat", "jti", "client_id", "workspace_id", "scope"]},
            leeway=30,  # 30s clock-skew tolerance
        )
    except jwt.PyJWTError as e:
        raise ValueError("invalid_token") from e
    return OAuthTokenClaims(
        sub=payload["sub"],
        client_id=payload["client_id"],
        workspace_id=payload["workspace_id"],
        scope=payload["scope"],
        audience=payload.get("aud"),
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
