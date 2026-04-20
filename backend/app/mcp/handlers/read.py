"""MCP read handlers. Stubs in Task 2.3; real impls in Task 2.5."""
from __future__ import annotations

import json

from app.mcp.auth import MCPContext


async def handle_ping(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({"ok": True, "version": "0.1.0", "active_slug": None})


async def handle_active(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({})


async def handle_list(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps([])


async def handle_get(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({})


async def handle_brief(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return ""


async def handle_search(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({"results": []})


async def handle_recent(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps([])


async def handle_claude_md(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return ""


async def handle_handover(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return ""
