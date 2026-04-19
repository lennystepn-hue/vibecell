import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_list_empty_returns_empty_items(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-empty@example.com")
            resp = await c.get("/api/v1/projects")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "next_cursor": None}


async def test_list_returns_created_projects(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-items@example.com")
            await c.post("/api/v1/projects", json={"slug": "butlr", "name": "Butlr"})
            await c.post("/api/v1/projects", json={"slug": "zapline", "name": "Zapline"})
            resp = await c.get("/api/v1/projects")
    finally:
        clear_db_override()
    body = resp.json()
    assert len(body["items"]) == 2
    slugs = {p["slug"] for p in body["items"]}
    assert slugs == {"butlr", "zapline"}


async def test_list_filter_by_status(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-filter@example.com")
            await c.post("/api/v1/projects", json={"slug": "bb", "name": "B", "status": "building"})
            await c.post("/api/v1/projects", json={"slug": "ll", "name": "L", "status": "live"})
            resp = await c.get("/api/v1/projects?status=live")
    finally:
        clear_db_override()
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["slug"] == "ll"


async def test_list_filter_by_q(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-q@example.com")
            await c.post("/api/v1/projects", json={"slug": "alpha", "name": "Alpha Service"})
            await c.post("/api/v1/projects", json={"slug": "beta", "name": "Beta Service"})
            resp = await c.get("/api/v1/projects?q=alpha")
    finally:
        clear_db_override()
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["slug"] == "alpha"


async def test_list_401_without_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/projects")
    assert resp.status_code == 401
