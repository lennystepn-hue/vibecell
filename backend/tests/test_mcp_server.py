import pytest

pytestmark = pytest.mark.integration


async def test_mcp_requires_auth(client) -> None:
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401


async def test_initialize_returns_server_info(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert body["result"]["protocolVersion"] == "2025-06-18"
    assert body["result"]["serverInfo"]["name"] == "vibecell"
    assert body["result"]["capabilities"]["tools"] == {}


async def test_ping_method(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 7, "method": "ping", "params": {},
    })
    assert resp.status_code == 200
    assert resp.json()["result"] == {}


async def test_unknown_method(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 8, "method": "not_a_method", "params": {},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32601
