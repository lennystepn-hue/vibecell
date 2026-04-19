import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_me_returns_user_and_active_workspace(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "me-test@example.com")
            resp = await c.get("/api/v1/me")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "me-test@example.com"
    assert body["active_workspace"]["slug"]
    assert body["active_workspace"]["plan"] == "free"
    assert len(body["workspaces"]) == 1
    assert body["workspaces"][0]["role"] == "owner"


async def test_me_returns_401_without_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["type"] == "/errors/unauthorized"
