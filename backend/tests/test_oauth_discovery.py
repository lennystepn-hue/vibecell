import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration


async def test_authorization_server_metadata() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    body = resp.json()
    assert body["issuer"] == "https://vibecell.dev"
    assert body["authorization_endpoint"] == "https://vibecell.dev/oauth/authorize"
    assert body["token_endpoint"] == "https://vibecell.dev/oauth/token"
    assert body["revocation_endpoint"] == "https://vibecell.dev/oauth/revoke"
    assert body["registration_endpoint"] == "https://vibecell.dev/oauth/register"
    assert "authorization_code" in body["grant_types_supported"]
    assert "refresh_token" in body["grant_types_supported"]
    assert "S256" in body["code_challenge_methods_supported"]
    assert "vibecell:tools" in body["scopes_supported"]


async def test_protected_resource_metadata() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"] == "https://vibecell.dev/mcp"
    assert body["authorization_servers"] == ["https://vibecell.dev"]
    assert body["bearer_methods_supported"] == ["header"]
