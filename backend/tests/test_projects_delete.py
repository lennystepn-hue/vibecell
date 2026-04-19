import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_delete_removes_project(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "del-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "gone", "name": "Gone"})
            r_del = await c.delete("/api/v1/projects/gone")
            r_get = await c.get("/api/v1/projects/gone")
    finally:
        clear_db_override()
    assert r_del.status_code == 204
    assert r_get.status_code == 404


async def test_delete_404_when_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "del-missing@example.com")
            resp = await c.delete("/api/v1/projects/nope")
    finally:
        clear_db_override()
    assert resp.status_code == 404
