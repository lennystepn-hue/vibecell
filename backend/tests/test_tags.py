import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_tags_list_empty(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-empty@example.com")
            resp = await c.get("/api/v1/tags")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    assert resp.json() == []


async def test_tags_create_and_list(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-create@example.com")
            r_c = await c.post("/api/v1/tags", json={"name": "backend", "color": "#8ab4ff"})
            r_l = await c.get("/api/v1/tags")
    finally:
        clear_db_override()
    assert r_c.status_code == 201
    assert r_c.json()["name"] == "backend"
    body = r_l.json()
    assert len(body) == 1
    assert body[0]["color"] == "#8ab4ff"


async def test_tags_create_rejects_duplicate_per_workspace(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-dup@example.com")
            await c.post("/api/v1/tags", json={"name": "dup"})
            r2 = await c.post("/api/v1/tags", json={"name": "dup"})
    finally:
        clear_db_override()
    assert r2.status_code == 409
