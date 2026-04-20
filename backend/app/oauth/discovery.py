"""OAuth / MCP discovery metadata endpoints (RFC 8414, RFC 9728)."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_BASE = "https://vibecell.dev"


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata() -> dict:
    return {
        "issuer": _BASE,
        "authorization_endpoint": f"{_BASE}/oauth/authorize",
        "token_endpoint": f"{_BASE}/oauth/token",
        "revocation_endpoint": f"{_BASE}/oauth/revoke",
        "registration_endpoint": f"{_BASE}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
        "scopes_supported": ["vibecell:tools"],
    }


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata() -> dict:
    return {
        "resource": f"{_BASE}/mcp",
        "authorization_servers": [_BASE],
        "scopes_supported": ["vibecell:tools"],
        "bearer_methods_supported": ["header"],
    }
