"""MCP Streamable HTTP endpoint — single POST /mcp with JSON-RPC dispatch.

Spec: MCP 2025-06 (Streamable HTTP transport).
"""
from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError

from app.mcp.audit import log_tool_call
from app.mcp.auth import MCPContext, require_mcp_context
from app.mcp.tools import TOOLS, TOOLS_BY_NAME


router = APIRouter()


def _ok(id_: int | str | None, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: int | str | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    ctx: Annotated[MCPContext, Depends(require_mcp_context)],
) -> dict:
    body = await request.json()
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "vibecell", "version": "0.1.0"},
        })

    if method == "ping":
        return _ok(req_id, {})

    if method == "tools/list":
        tools_out = []
        for t in TOOLS:
            tools_out.append({
                "name": t.name,
                "description": t.description,
                "inputSchema": t.args_schema.model_json_schema(),
            })
        return _ok(req_id, {"tools": tools_out})

    if method == "tools/call":
        return await _dispatch_tool_call(ctx, req_id, params)

    return _err(req_id, -32601, f"Method not found: {method}")


async def _dispatch_tool_call(ctx: MCPContext, req_id: Any, params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    tool = TOOLS_BY_NAME.get(name or "")
    if tool is None:
        return _err(req_id, -32602, f"Unknown tool: {name}")

    try:
        args_model = tool.args_schema.model_validate(arguments)
    except ValidationError as e:
        return _err(req_id, -32602, f"Invalid arguments: {e.errors()}")

    t0 = time.monotonic()
    try:
        text = await tool.handler(args_model, ctx)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        await log_tool_call(
            db=ctx.db, client_id=ctx.client_id, workspace_id=ctx.workspace_id, user_id=ctx.user_id,
            tool_name=name, duration_ms=int((time.monotonic() - t0) * 1000), status="error",
        )
        return _err(req_id, -32603, f"Internal error: {type(exc).__name__}")

    await log_tool_call(
        db=ctx.db, client_id=ctx.client_id, workspace_id=ctx.workspace_id, user_id=ctx.user_id,
        tool_name=name, duration_ms=int((time.monotonic() - t0) * 1000), status=status,
    )
    return _ok(req_id, {"content": [{"type": "text", "text": text}]})
