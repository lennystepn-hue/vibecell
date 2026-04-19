import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_patch_workspace_name(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "patch-ws@example.com")
            r = await c.get("/api/v1/workspaces")
            slug = r.json()[0]["slug"]
            resp = await c.patch(f"/api/v1/workspaces/{slug}", json={"name": "Renamed"})
    finally:
        clear_db_override()

    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
