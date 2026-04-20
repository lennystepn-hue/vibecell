"""Full OAuth 2.1 spec flow against the live backend.
register → authorize → grant → token → refresh → revoke.
"""
import base64
import hashlib

import pytest

pytestmark = pytest.mark.integration


async def test_full_oauth_lifecycle(client, authed_client, user_workspace) -> None:
    # 1. Discovery
    meta = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert meta["issuer"]

    # 2. Register
    reg = (await client.post("/oauth/register", json={
        "client_name": "e2e-test",
        "redirect_uris": ["http://127.0.0.1:1/cb"],
    })).json()
    cid = reg["client_id"]

    # 3. Authorize (signed-in user)
    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=e2e&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )

    # 4. Grant
    g = await authed_client.post(
        "/oauth/grant",
        json={"state": "e2e", "workspace_id": user_workspace.id},
        follow_redirects=False,
    )
    code = g.headers["location"].split("code=")[1].split("&")[0]

    # 5. Token (code → access + refresh)
    tok = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": "http://127.0.0.1:1/cb",
        "client_id": cid, "code_verifier": verifier,
    })).json()
    assert "access_token" in tok
    assert "refresh_token" in tok
    assert tok["token_type"] == "Bearer"

    # 6. Refresh
    refresh_resp = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": cid,
    })
    assert refresh_resp.status_code == 200
    new_tok = refresh_resp.json()
    assert new_tok["refresh_token"] != tok["refresh_token"]

    # 7. Revoke refresh
    revoke_resp = await client.post("/oauth/revoke", data={
        "token": new_tok["refresh_token"], "token_type_hint": "refresh_token",
    })
    assert revoke_resp.status_code == 200

    # 8. Attempting to use revoked refresh → invalid_grant
    bad = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": new_tok["refresh_token"], "client_id": cid,
    })
    assert bad.status_code == 400
