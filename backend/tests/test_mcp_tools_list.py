import pytest

pytestmark = pytest.mark.integration


async def test_tools_list_returns_full_registry(mcp_client) -> None:
    """tools/list must return every Tool in the registry. Tool count grows
    over time so we use a sane range instead of a hard-coded number."""
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    assert resp.status_code == 200
    tools = resp.json()["result"]["tools"]
    assert 30 <= len(tools) <= 60
    names = {t["name"] for t in tools}
    # Pinned-name sanity checks — present + correctly de-dotted.
    assert "vibecell_ping" in names
    assert "vibecell.ping" not in names    # underscore form only on the wire
    assert "vibecell_run" not in names     # explicitly excluded everywhere
    for t in tools:
        assert t["name"].startswith("vibecell_")
        assert isinstance(t["description"], str)
        assert "inputSchema" in t
