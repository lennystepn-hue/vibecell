import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def _setup_github_connected(
    c: AsyncClient, session: AsyncSession, email: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sign in + attach a fake github integration via OAuth callback."""
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake_token",
        "me": {"login": "lenny"},
    })
    await sign_in(c, session, email)
    me = (await c.get("/api/v1/me")).json()
    ws_slug = me["active_workspace"]["slug"]

    from sqlalchemy import select

    from app.models import User, Workspace
    ws_id = (await session.execute(
        select(Workspace.id).where(Workspace.slug == ws_slug)
    )).scalar_one()
    user_id = (await session.execute(
        select(User.id).where(User.email == email)
    )).scalar_one()

    redis = await get_redis()
    state = f"state-{email}"
    await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)
    r = await c.get(f"/api/v1/integrations/github/oauth-callback?code=c&state={state}")
    assert r.status_code == 303


async def test_list_repos_returns_normalized_response(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await _setup_github_connected(c, session, "repos-list@example.com", monkeypatch)

            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake_token",
                "me": {"login": "lenny"},
                "list_user_repos": [
                    {
                        "name": "butlr",
                        "owner": {"login": "lenny"},
                        "full_name": "lenny/butlr",
                        "description": "Openclaw",
                        "private": True,
                        "default_branch": "main",
                        "language": "Python",
                        "license": {"spdx_id": "MIT"},
                        "homepage": "https://butlr.cloud",
                        "clone_url": "https://github.com/lenny/butlr.git",
                        "pushed_at": "2026-04-18T10:00:00Z",
                    },
                ],
            })
            resp = await c.get("/api/v1/integrations/github/repos")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["owner"] == "lenny"
    assert body[0]["name"] == "butlr"
    assert body[0]["language"] == "Python"
    assert body[0]["license_spdx"] == "MIT"
