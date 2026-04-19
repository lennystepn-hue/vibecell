import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_patch_updates_fields(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "patch-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "proj", "name": "Original"})
            resp = await c.patch(
                "/api/v1/projects/proj",
                json={"name": "Renamed", "status": "live"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["status"] == "live"


async def test_patch_archived_sets_archived_at(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "archive-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "old", "name": "Old"})
            resp = await c.patch("/api/v1/projects/old", json={"status": "archived"})
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "archived"
    assert body["archived_at"] is not None
