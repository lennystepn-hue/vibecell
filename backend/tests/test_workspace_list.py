import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_list_workspaces_returns_default_on_first_login(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-test@example.com")
            resp = await c.get("/api/v1/workspaces")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["role"] == "owner"
    assert body[0]["plan"] == "free"


async def test_list_workspaces_401_without_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/workspaces")
    assert resp.status_code == 401
