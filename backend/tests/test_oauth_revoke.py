"""Integration tests for POST /oauth/revoke — RFC 7009 token revocation."""
import pytest

pytestmark = pytest.mark.integration


async def test_revoke_access_token_blacklists_jti(client, issued_token_pair) -> None:
    access = issued_token_pair["access_token"]
    resp = await client.post("/oauth/revoke", data={"token": access, "token_type_hint": "access_token"})
    assert resp.status_code == 200

    from app.oauth.tokens import JTIBlacklist, verify_access_token
    claims = verify_access_token(access)
    assert await JTIBlacklist().is_revoked(claims.jti)


async def test_revoke_refresh_token_invalidates(client, issued_token_pair) -> None:
    rt = issued_token_pair["refresh_token"]
    resp = await client.post("/oauth/revoke", data={"token": rt, "token_type_hint": "refresh_token"})
    assert resp.status_code == 200

    cid = issued_token_pair["client_id"]
    again = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
    })
    assert again.status_code == 400


async def test_revoke_unknown_token_returns_200(client) -> None:
    """RFC 7009: return 200 regardless of token validity."""
    resp = await client.post("/oauth/revoke", data={"token": "rt_nonexistent", "token_type_hint": "refresh_token"})
    assert resp.status_code == 200
