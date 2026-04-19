import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_create_workspace_happy_path(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "create-ws@example.com")
            resp = await c.post("/api/v1/workspaces", json={"slug": "lab", "name": "Lab"})
    finally:
        clear_db_override()

    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "lab"
    assert body["name"] == "Lab"
    assert body["plan"] == "free"


async def test_create_workspace_rejects_reserved_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "reserved@example.com")
            resp = await c.post("/api/v1/workspaces", json={"slug": "admin", "name": "X"})
    finally:
        clear_db_override()

    assert resp.status_code == 400
    assert resp.json()["type"] == "/errors/validation"


async def test_create_workspace_rejects_duplicate_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "dup@example.com")
            r1 = await c.post("/api/v1/workspaces", json={"slug": "duplo", "name": "A"})
            assert r1.status_code == 201
            r2 = await c.post("/api/v1/workspaces", json={"slug": "duplo", "name": "B"})
    finally:
        clear_db_override()

    assert r2.status_code == 409
    assert r2.json()["type"] == "/errors/conflict"


async def test_create_workspace_rejects_malformed_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "bad-slug@example.com")
            resp = await c.post("/api/v1/workspaces", json={"slug": "BAD SLUG", "name": "X"})
    finally:
        clear_db_override()

    assert resp.status_code == 422
