import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_attach_and_detach_stack(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r_a = await c.post(
                "/api/v1/projects/pa/stack",
                json={"stack_item_slug": "fastapi", "role": "primary"},
            )
            assert r_a.status_code == 201
            assert r_a.json()["stack_item_slug"] == "fastapi"

            r_dup = await c.post(
                "/api/v1/projects/pa/stack",
                json={"stack_item_slug": "fastapi"},
            )
            assert r_dup.status_code == 409

            r_d = await c.delete("/api/v1/projects/pa/stack/fastapi")
    finally:
        clear_db_override()
    assert r_d.status_code == 204


async def test_stack_404_for_unknown_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-404@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r = await c.post(
                "/api/v1/projects/pa/stack", json={"stack_item_slug": "nonexistent"},
            )
    finally:
        clear_db_override()
    assert r.status_code == 404
