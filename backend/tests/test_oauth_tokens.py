import os

import pytest

# Provide a dummy DB URL so get_settings() validates in tests that don't use
# the session-scoped `engine` fixture (which normally injects this var).
os.environ.setdefault("HANGAR_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")

from app.oauth.tokens import (
    JTIBlacklist,
    OAuthTokenClaims,
    hash_refresh_token,
    issue_access_token,
    issue_refresh_token,
    verify_access_token,
)


def test_issue_and_verify_roundtrip() -> None:
    claims = OAuthTokenClaims(
        sub="01USR",
        client_id="dyn_c",
        workspace_id="01WSP",
        scope="vibecell:tools",
    )
    jwt_str, jti = issue_access_token(claims)
    decoded = verify_access_token(jwt_str)
    assert decoded.sub == "01USR"
    assert decoded.client_id == "dyn_c"
    assert decoded.workspace_id == "01WSP"
    assert decoded.jti == jti
    assert decoded.exp > decoded.iat


def test_verify_rejects_tampered_token() -> None:
    claims = OAuthTokenClaims(sub="01USR", client_id="c", workspace_id="w", scope="vibecell:tools")
    jwt_str, _ = issue_access_token(claims)
    tampered = jwt_str[:-4] + "aaaa"
    with pytest.raises(ValueError):
        verify_access_token(tampered)


def test_verify_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    monkeypatch.setenv("HANGAR_OAUTH_ACCESS_TOKEN_TTL_SECONDS", "-100")
    get_settings.cache_clear()
    claims = OAuthTokenClaims(sub="01USR", client_id="c", workspace_id="w", scope="vibecell:tools")
    jwt_str, _ = issue_access_token(claims)
    with pytest.raises(ValueError):
        verify_access_token(jwt_str)


def test_refresh_token_hash_stable() -> None:
    t = "rt_abc123"
    assert hash_refresh_token(t) == hash_refresh_token(t)
    assert hash_refresh_token(t) != hash_refresh_token("rt_xyz")


def test_issue_refresh_token_is_opaque_and_hashable() -> None:
    token = issue_refresh_token()
    assert token.startswith("rt_")
    assert len(token) == 67
    h = hash_refresh_token(token)
    assert len(h) == 64  # sha256 hex


def test_verify_rejects_token_signed_with_wrong_secret(monkeypatch) -> None:
    """Token signed with a different secret must fail verification."""
    import jwt
    from app.core.config import get_settings

    # Issue a "token" directly with a different secret (simulates a different authority)
    payload = {
        "iss": "https://vibecell.dev",
        "aud": "https://vibecell.dev/mcp",
        "sub": "01USR", "client_id": "c", "workspace_id": "w", "scope": "vibecell:tools",
        "iat": 0, "exp": 9999999999, "jti": "j",
    }
    tok = jwt.encode(payload, "different_secret_" + "x" * 50, algorithm="HS256")
    with pytest.raises(ValueError):
        verify_access_token(tok)


def test_verify_rejects_missing_required_claim(monkeypatch) -> None:
    """Token missing a required claim (e.g. workspace_id) must fail."""
    import jwt
    from app.core.config import get_settings

    s = get_settings()
    payload = {
        "iss": "https://vibecell.dev",
        "aud": "https://vibecell.dev/mcp",
        "sub": "01USR", "client_id": "c", "scope": "vibecell:tools",
        # NO workspace_id
        "iat": 0, "exp": 9999999999, "jti": "j",
    }
    tok = jwt.encode(payload, s.oauth_jwt_secret, algorithm="HS256")
    with pytest.raises(ValueError):
        verify_access_token(tok)


@pytest.mark.integration
async def test_jti_blacklist_rejects_non_positive_ttl() -> None:
    """add() with ttl_seconds <= 0 should be a no-op (not block 1-second revocation)."""
    bl = JTIBlacklist()
    await bl.add("jti_expired", ttl_seconds=0)
    assert not await bl.is_revoked("jti_expired")

    await bl.add("jti_negative", ttl_seconds=-5)
    assert not await bl.is_revoked("jti_negative")


@pytest.mark.integration
async def test_jti_blacklist_roundtrip() -> None:
    bl = JTIBlacklist()
    await bl.add("jti_123", ttl_seconds=60)
    assert await bl.is_revoked("jti_123")
    assert not await bl.is_revoked("jti_never_added")


@pytest.mark.integration
async def test_jti_blacklist_ttl_expires() -> None:
    import asyncio
    bl = JTIBlacklist()
    await bl.add("jti_shortlived", ttl_seconds=1)
    await asyncio.sleep(1.2)
    assert not await bl.is_revoked("jti_shortlived")
