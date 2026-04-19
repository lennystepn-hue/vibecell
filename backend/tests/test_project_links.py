import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_link_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "links@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r_c = await c.post(
                "/api/v1/projects/pa/links",
                json={"kind": "live", "label": "Production", "url": "https://x.com"},
            )
            assert r_c.status_code == 201
            lid = r_c.json()["id"]
            r_u = await c.patch(
                f"/api/v1/projects/pa/links/{lid}",
                json={"label": "Updated"},
            )
            assert r_u.status_code == 200
            r_d = await c.delete(f"/api/v1/projects/pa/links/{lid}")
    finally:
        clear_db_override()
    assert r_d.status_code == 204
