"""register → authorize → token → mcp initialize → tools/list → tools/call (ping)."""
import base64
import hashlib

import pytest

pytestmark = pytest.mark.integration


async def test_end_to_end_oauth_and_mcp(client, authed_client, user_workspace_with_active_project) -> None:
    reg = (await client.post("/oauth/register", json={
        "client_name": "mcp-e2e",
        "redirect_uris": ["http://127.0.0.1:1/cb"],
    })).json()
    cid = reg["client_id"]

    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=mcp-e2e&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    ws_id = user_workspace_with_active_project["workspace"].id
    g = await authed_client.post(
        "/oauth/grant",
        json={"state": "mcp-e2e", "workspace_id": ws_id},
        follow_redirects=False,
    )
    code = g.headers["location"].split("code=")[1].split("&")[0]

    tok = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": "http://127.0.0.1:1/cb",
        "client_id": cid, "code_verifier": verifier,
    })).json()

    client.headers["Authorization"] = f"Bearer {tok['access_token']}"

    # 1. initialize
    init = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
    })).json()
    assert init["result"]["serverInfo"]["name"] == "vibecell"
    assert init["result"]["protocolVersion"] == "2025-06-18"

    # 2. tools/list returns the full registry. Count grows over time as we add
    # tools — assert a sane range instead of pinning a historic number.
    tl = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })).json()
    assert 30 <= len(tl["result"]["tools"]) <= 60

    # 3. tools/call vibecell.ping — exercises auth middleware + dispatcher + audit log
    ping = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "vibecell.ping", "arguments": {}},
    })).json()
    assert "content" in ping["result"]
    ping_text = ping["result"]["content"][0]["text"]
    import json
    ping_data = json.loads(ping_text)
    assert ping_data["ok"] is True
    assert ping_data["active_slug"] == "vibecell"

    # 4. tools/call vibecell.list — should include our seeded project
    list_resp = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "vibecell.list", "arguments": {}},
    })).json()
    list_data = json.loads(list_resp["result"]["content"][0]["text"])
    assert any(p["slug"] == "vibecell" for p in list_data)
