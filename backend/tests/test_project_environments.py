import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_environment_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "envs@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r = await c.post(
                "/api/v1/projects/pa/environments",
                json={"kind": "prod", "url": "https://x.com"},
            )
            assert r.status_code == 201
            env_id = r.json()["id"]
            r_patch = await c.patch(
                f"/api/v1/projects/pa/environments/{env_id}",
                json={"url": "https://y.com"},
            )
            assert r_patch.status_code == 200
            assert r_patch.json()["url"] == "https://y.com"
            r_del = await c.delete(f"/api/v1/projects/pa/environments/{env_id}")
            assert r_del.status_code == 204
    finally:
        clear_db_override()


async def test_environment_rejects_invalid_kind(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "envs-bad@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r = await c.post(
                "/api/v1/projects/pa/environments", json={"kind": "nope"},
            )
    finally:
        clear_db_override()
    assert r.status_code == 422
