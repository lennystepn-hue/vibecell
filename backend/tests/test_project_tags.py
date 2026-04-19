import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_attach_tag_by_name_creates_tag(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r_a = await c.post(
                "/api/v1/projects/pa/tags",
                json={"name": "backend", "color": "#8ab4ff"},
            )
    finally:
        clear_db_override()
    assert r_a.status_code == 201
    body = r_a.json()
    assert body["name"] == "backend"
    assert body["color"] == "#8ab4ff"


async def test_detach_tag_by_id(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-del@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r_a = await c.post(
                "/api/v1/projects/pa/tags", json={"name": "frontend"},
            )
            tag_id = r_a.json()["id"]
            r_d = await c.delete(f"/api/v1/projects/pa/tags/{tag_id}")
    finally:
        clear_db_override()
    assert r_d.status_code == 204
