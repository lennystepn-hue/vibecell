import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_get_workspace_by_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "get-ws@example.com")
            # First list to discover the default workspace slug
            r = await c.get("/api/v1/workspaces")
            slug = r.json()[0]["slug"]
            resp = await c.get(f"/api/v1/workspaces/{slug}")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    assert resp.json()["slug"] == slug


async def test_get_workspace_404_when_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "missing@example.com")
            resp = await c.get("/api/v1/workspaces/nonexistent")
    finally:
        clear_db_override()

    assert resp.status_code == 404


async def test_get_workspace_403_when_not_member(session: AsyncSession) -> None:
    # User A creates a workspace "private-a", user B tries to access it
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "owner-a@example.com")
            await c.post("/api/v1/workspaces", json={"slug": "private-a", "name": "A"})
            # switch to user B
            await c.post("/api/v1/auth/logout")
            await sign_in(c, session, "user-b@example.com")
            resp = await c.get("/api/v1/workspaces/private-a")
    finally:
        clear_db_override()

    assert resp.status_code == 403
