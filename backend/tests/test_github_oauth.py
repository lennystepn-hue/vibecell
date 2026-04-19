import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import Integration
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def test_oauth_start_redirects_to_github(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-start@example.com")
            resp = await c.get("/api/v1/integrations/github/oauth-start")
    finally:
        clear_db_override()
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize?")
    assert "state=" in location


async def test_oauth_callback_stores_encrypted_token(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake_token_123",
        "me": {"login": "lenny", "avatar_url": "https://avatar"},
    })
    # Pre-plant an OAuth state in Redis
    redis = await get_redis()
    state = "teststate123"
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-cb@example.com")
            # Pull the workspace_id + user_id from /me
            me = (await c.get("/api/v1/me")).json()
            ws_slug = me["active_workspace"]["slug"]
            from app.models import User, Workspace
            ws_id = (await session.execute(
                select(Workspace.id).where(Workspace.slug == ws_slug)
            )).scalar_one()
            user_id = (await session.execute(
                select(User.id).where(User.email == "oauth-cb@example.com")
            )).scalar_one()

            await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)

            resp = await c.get(
                f"/api/v1/integrations/github/oauth-callback?code=fake&state={state}"
            )
    finally:
        clear_db_override()

    assert resp.status_code == 303
    assert resp.headers["location"] == "/import/github"

    integ = (await session.execute(
        select(Integration).where(
            Integration.workspace_id == ws_id, Integration.kind == "github"
        )
    )).scalar_one()
    assert integ.token_ciphertext is not None
    assert integ.config.get("login") == "lenny"


async def test_oauth_callback_rejects_expired_state(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-expired@example.com")
            resp = await c.get(
                "/api/v1/integrations/github/oauth-callback?code=fake&state=nonexistent"
            )
    finally:
        clear_db_override()
    assert resp.status_code == 400
    assert resp.json()["type"] == "/errors/oauth-state"


async def test_delete_github_integration(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake",
        "me": {"login": "x"},
    })
    redis = await get_redis()
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-del@example.com")
            me = (await c.get("/api/v1/me")).json()
            ws_slug = me["active_workspace"]["slug"]
            from app.models import User, Workspace
            ws_id = (await session.execute(
                select(Workspace.id).where(Workspace.slug == ws_slug)
            )).scalar_one()
            user_id = (await session.execute(
                select(User.id).where(User.email == "oauth-del@example.com")
            )).scalar_one()

            state = "deltest"
            await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)
            await c.get(f"/api/v1/integrations/github/oauth-callback?code=c&state={state}")

            resp = await c.delete("/api/v1/integrations/github")
    finally:
        clear_db_override()
    assert resp.status_code == 204


async def test_integrations_list(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "integrations-list@example.com")
            resp = await c.get("/api/v1/integrations")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    assert resp.json() == []
