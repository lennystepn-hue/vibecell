"""MCP Streamable HTTP endpoint — single POST /mcp with JSON-RPC dispatch.

Spec: MCP 2025-06 (Streamable HTTP transport).
"""
from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError

from app.mcp.audit import log_tool_call
from app.mcp.auth import MCPContext, require_mcp_context
from app.mcp.tools import TOOLS, resolve_tool
from app.metrics.registry import mcp_tool_calls
from app.services import presence as presence_svc
from app.services.access_level import access_level_for_user

router = APIRouter()


def _ok(id_: int | str | None, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: int | str | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


@router.post("/")
@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    ctx: Annotated[MCPContext, Depends(require_mcp_context)],
):
    body = await request.json()
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    # JSON-RPC notifications (no id) — server MUST NOT respond with a body.
    if req_id is None:
        return Response(status_code=202)

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
    raw_name = params.get("name")
    arguments = params.get("arguments") or {}
    tool = resolve_tool(raw_name or "") if isinstance(raw_name, str) else None
    if tool is None or not isinstance(raw_name, str):
        return _err(req_id, -32602, f"Unknown tool: {raw_name}")
    name: str = raw_name

    try:
        args_model = tool.args_schema.model_validate(arguments)
    except ValidationError as e:
        return _err(req_id, -32602, f"Invalid arguments: {e.errors()}")

    # Spec-6 plan-gate: read-only mode blocks all write tools. The `is_write`
    # property derives from the handler's module path (handlers/write.py vs
    # handlers/read.py) so it stays accurate as new tools land. Read-only
    # users can still call read tools (vibecell_active, _search, _get,
    # _activity, _audit, AI generators that don't persist, etc.) so they
    # can audit their own data + decide whether to renew.
    if tool.is_write:
        level = await access_level_for_user(ctx.db, ctx.user_id)
        if level != "full":
            mcp_tool_calls.labels(tool_name=name, status="read_only").inc()
            return _err(
                req_id,
                # JSON-RPC application-level error code. -32002 is unused in
                # the JSON-RPC spec; we co-opt it for "subscription required".
                -32002,
                "Subscription expired — Vibecell is read-only. "
                "Renew at https://vibecell.dev/settings/billing to keep "
                "logging sessions, decisions, and ships.",
            )

    # Resolve which project this tool touched BEFORE running it, so the audit
    # log row (and downstream presence ping) is correctly attributed. Tools
    # that take an explicit slug / project arg win over the active-project
    # fallback. Workspace-scoped tools (list, search, switch, ping, …) leave
    # this NULL so the activity feed doesn't smear them across projects.
    touched_slug: str | None = (
        getattr(args_model, "slug", None)
        or getattr(args_model, "project", None)
    )
    if not touched_slug and _is_project_scoped(name or ""):
        try:
            touched_slug = await _active_project_slug(ctx)
        except Exception:
            touched_slug = None

    t0 = time.monotonic()
    try:
        text = await tool.handler(args_model, ctx)
        status = "ok"
    except Exception as exc:
        await ctx.db.rollback()
        await log_tool_call(
            db=ctx.db, client_id=ctx.client_id, workspace_id=ctx.workspace_id, user_id=ctx.user_id,
            tool_name=name, duration_ms=int((time.monotonic() - t0) * 1000), status="error",
            project_slug=touched_slug,
        )
        await ctx.db.commit()
        mcp_tool_calls.labels(tool_name=name, status="error").inc()
        return _err(req_id, -32603, f"Internal error: {type(exc).__name__}")

    await log_tool_call(
        db=ctx.db, client_id=ctx.client_id, workspace_id=ctx.workspace_id, user_id=ctx.user_id,
        tool_name=name, duration_ms=int((time.monotonic() - t0) * 1000), status=status,
        project_slug=touched_slug,
    )
    await ctx.db.commit()
    mcp_tool_calls.labels(tool_name=name, status=status).inc()

    # Presence ping — same touched_slug we just stamped on the audit row.
    if touched_slug:
        try:
            await presence_svc.mark_live(
                workspace_id=ctx.workspace_id,
                project_slug=touched_slug,
                tool_name=name,
                session_id=ctx.client_id,
            )
        except Exception:
            pass

    # Layer-2 of the auto-logging safety net: every tool response carries a
    # `_audit_hint` block when drift is detected (commits arriving without
    # corresponding session logs, todos that look done, stale focus). The
    # SKILL has a hard rule that says "if _audit_hint.suggested_action is
    # set, run it before your next user-facing response" — this forces the
    # discipline mechanically rather than via the SKILL's good intentions.
    result_payload: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    try:
        if touched_slug:
            from sqlalchemy import select as _select

            from app.models import Project as _Project
            from app.services.audit_hint import compute_audit_hint

            proj_row = (
                await ctx.db.execute(
                    _select(_Project)
                    .where(_Project.workspace_id == ctx.workspace_id)
                    .where(_Project.slug == touched_slug)
                )
            ).scalar_one_or_none()
            hint = await compute_audit_hint(ctx.db, project=proj_row)
            if hint is not None:
                result_payload["_audit_hint"] = hint.to_dict()
    except Exception:
        # Hint computation MUST NOT fail a tool call — it's advisory.
        pass

    return _ok(req_id, result_payload)


# Tools that operate on the WORKSPACE, not on a specific project. For these
# we don't fall back to the active-project slug — leaving project_slug NULL
# means "this tool wasn't about any single project" so the per-project
# activity feed correctly excludes them.
_WORKSPACE_SCOPED_TOOLS: frozenset[str] = frozenset({
    "vibecell_ping",
    "vibecell_list",
    "vibecell_search",
    "vibecell_recent_projects",
    "vibecell_switch",  # changes which project IS active; not "about" the new one in audit terms
})


def _is_project_scoped(tool_name: str) -> bool:
    """Should a NULL slug fall back to the active project for this tool?"""
    return tool_name not in _WORKSPACE_SCOPED_TOOLS


async def _active_project_slug(ctx: MCPContext) -> str | None:
    """Look up the active project's slug for this workspace, if any."""
    from sqlalchemy import select

    from app.models import ActiveProject, Project

    row = (await ctx.db.execute(
        select(Project.slug)
        .join(ActiveProject, ActiveProject.project_id == Project.id)
        .where(ActiveProject.workspace_id == ctx.workspace_id)
    )).scalar_one_or_none()
    return row
