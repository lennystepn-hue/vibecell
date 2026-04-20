"""MCP write handlers. Stubs in Task 2.3; real impls in Task 2.6."""
from __future__ import annotations

import json

from app.mcp.auth import MCPContext


async def handle_switch(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_log_session(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_update_context(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_decision(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_idea(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_note_append(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_ship(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
async def handle_status(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa: ARG001, E501
