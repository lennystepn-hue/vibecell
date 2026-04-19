import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_command_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "cmds@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r_c = await c.post(
                "/api/v1/projects/pa/commands",
                json={"label": "Deploy", "command": "make deploy"},
            )
            assert r_c.status_code == 201
            cid = r_c.json()["id"]
            r_u = await c.patch(
                f"/api/v1/projects/pa/commands/{cid}",
                json={"run_in": "background"},
            )
            assert r_u.status_code == 200
            assert r_u.json()["run_in"] == "background"
            r_d = await c.delete(f"/api/v1/projects/pa/commands/{cid}")
    finally:
        clear_db_override()
    assert r_d.status_code == 204
