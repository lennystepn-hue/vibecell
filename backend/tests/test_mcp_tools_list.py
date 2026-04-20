import pytest

pytestmark = pytest.mark.integration


async def test_tools_list_returns_all_17(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    assert resp.status_code == 200
    tools = resp.json()["result"]["tools"]
    assert len(tools) == 17
    names = {t["name"] for t in tools}
    assert "vibecell.ping" in names
    assert "vibecell.run" not in names
    for t in tools:
        assert t["name"].startswith("vibecell.")
        assert isinstance(t["description"], str)
        assert "inputSchema" in t
