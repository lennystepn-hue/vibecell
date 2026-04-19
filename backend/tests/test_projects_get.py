import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_get_by_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "get-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "my-p", "name": "MyP"})
            resp = await c.get("/api/v1/projects/my-p")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-p"


async def test_get_404_when_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "get-missing@example.com")
            resp = await c.get("/api/v1/projects/nonexistent")
    finally:
        clear_db_override()
    assert resp.status_code == 404
