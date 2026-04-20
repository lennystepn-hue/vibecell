"""OAuth / MCP discovery metadata endpoints (RFC 8414, RFC 9728)."""
from __future__ import annotations

import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()

_BASE = "https://vibecell.dev"


def _n_e_from_pubkey_pem(pem_bytes: bytes) -> tuple[str, str]:
    key = serialization.load_pem_public_key(pem_bytes, backend=default_backend())
    nums = key.public_numbers()

    def _b64(n: int) -> str:
        byte_length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()

    return _b64(nums.n), _b64(nums.e)


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
        "jwks_uri": f"{_BASE}/.well-known/jwks.json",
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata() -> dict:
    return {
        "resource": f"{_BASE}/mcp",
        "authorization_servers": [_BASE],
        "scopes_supported": ["vibecell:tools"],
        "bearer_methods_supported": ["header"],
    }


@router.get("/.well-known/jwks.json")
async def jwks_endpoint() -> dict:
    s = get_settings()
    if not s.oauth_public_key_b64:
        return {"keys": []}
    pem = base64.b64decode(s.oauth_public_key_b64)
    n, e = _n_e_from_pubkey_pem(pem)
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": s.oauth_jwt_kid,
                "n": n,
                "e": e,
            }
        ]
    }
