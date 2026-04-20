import os

# Provide a dummy DB URL so get_settings() validates in tests that don't use
# the session-scoped `engine` fixture (which normally injects this var).
os.environ.setdefault("HANGAR_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")

from collections.abc import AsyncIterator
from typing import Annotated
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.mcp.auth import MCPContext, require_mcp_context
from app.oauth.tokens import JTIBlacklist, OAuthTokenClaims, issue_access_token

pytestmark = pytest.mark.integration


def _build_probe_app() -> FastAPI:
    app = FastAPI()

    # Override get_db with a no-op mock so tests don't need a real DB.
    async def _mock_db() -> AsyncIterator[AsyncSession]:
        yield AsyncMock(spec=AsyncSession)

    app.dependency_overrides[get_db] = _mock_db

    @app.get("/probe")
    async def probe(ctx: Annotated[MCPContext, Depends(require_mcp_context)]):
        return {"user": ctx.user_id, "workspace": ctx.workspace_id, "client": ctx.client_id}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_probe_requires_bearer():
    app = _build_probe_app()
    async with await _client(app) as c:
        r = await c.get("/probe")
        assert r.status_code == 401
        assert "resource_metadata" in r.headers.get("www-authenticate", "")


async def test_probe_rejects_garbage_token():
    app = _build_probe_app()
    async with await _client(app) as c:
        r = await c.get("/probe", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401


async def test_probe_rejects_expired(monkeypatch):
    monkeypatch.setenv("HANGAR_OAUTH_ACCESS_TOKEN_TTL_SECONDS", "-60")
    from app.core.config import get_settings
    get_settings.cache_clear()
    tok, _ = issue_access_token(OAuthTokenClaims(sub="u", client_id="c", workspace_id="w", scope="vibecell:tools"))
    app = _build_probe_app()
    async with await _client(app) as c:
        r = await c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


async def test_probe_rejects_revoked_jti():
    tok, jti = issue_access_token(OAuthTokenClaims(sub="u", client_id="c", workspace_id="w", scope="vibecell:tools"))
    await JTIBlacklist().add(jti, ttl_seconds=60)
    app = _build_probe_app()
    async with await _client(app) as c:
        r = await c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


async def test_probe_rejects_wrong_scope():
    tok, _ = issue_access_token(OAuthTokenClaims(sub="u", client_id="c", workspace_id="w", scope="other"))
    app = _build_probe_app()
    # JTI blacklist returns False (not revoked) — no Redis needed.
    with patch.object(JTIBlacklist, "is_revoked", new=AsyncMock(return_value=False)):
        async with await _client(app) as c:
            r = await c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 403


async def test_probe_accepts_valid():
    tok, _ = issue_access_token(OAuthTokenClaims(sub="u1", client_id="c1", workspace_id="w1", scope="vibecell:tools"))
    app = _build_probe_app()
    # JTI blacklist returns False (not revoked) — no Redis needed.
    with patch.object(JTIBlacklist, "is_revoked", new=AsyncMock(return_value=False)):
        async with await _client(app) as c:
            r = await c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 200
            assert r.json() == {"user": "u1", "workspace": "w1", "client": "c1"}
