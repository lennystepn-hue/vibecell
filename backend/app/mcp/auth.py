"""Bearer-JWT middleware for the /mcp endpoint. Yields an MCPContext.

On failure, returns 401 with WWW-Authenticate pointing at the protected-resource metadata
— required by MCP clients to auto-start the OAuth dance.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.metrics.registry import mcp_auth_failures
from app.oauth.tokens import JTIBlacklist, verify_access_token

_METADATA_URL = "https://vibecell.dev/.well-known/oauth-protected-resource"
_WWW_AUTH_HEADER = {"WWW-Authenticate": f'Bearer resource_metadata="{_METADATA_URL}"'}


@dataclass(frozen=True, slots=True)
class MCPContext:
    db: AsyncSession
    user_id: str
    workspace_id: str
    client_id: str
    jti: str
    scope: str


async def require_mcp_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MCPContext:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        mcp_auth_failures.labels(reason="missing_bearer").inc()
        raise HTTPException(status_code=401, detail="missing_bearer", headers=_WWW_AUTH_HEADER)

    token = header[7:].strip()
    try:
        claims = verify_access_token(token)
    except ValueError as e:
        mcp_auth_failures.labels(reason="invalid_token").inc()
        raise HTTPException(status_code=401, detail="invalid_token", headers=_WWW_AUTH_HEADER) from e

    if await JTIBlacklist().is_revoked(claims.jti):
        mcp_auth_failures.labels(reason="revoked_token").inc()
        raise HTTPException(status_code=401, detail="revoked_token", headers=_WWW_AUTH_HEADER)

    if "vibecell:tools" not in claims.scope.split():
        mcp_auth_failures.labels(reason="insufficient_scope").inc()
        raise HTTPException(status_code=403, detail="insufficient_scope", headers=_WWW_AUTH_HEADER)

    return MCPContext(
        db=db,
        user_id=claims.sub,
        workspace_id=claims.workspace_id,
        client_id=claims.client_id,
        jti=claims.jti,
        scope=claims.scope,
    )
