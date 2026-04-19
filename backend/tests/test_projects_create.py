import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_create_happy_path(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "create-p@example.com")
            resp = await c.post(
                "/api/v1/projects",
                json={"slug": "butlr", "name": "Butlr", "emoji": "🛎️", "pitch": "OpenClaw-as-a-Service"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "butlr"
    assert body["emoji"] == "🛎️"
    assert body["status"] == "building"  # default


async def test_create_rejects_reserved_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "reserved-p@example.com")
            resp = await c.post("/api/v1/projects", json={"slug": "api", "name": "X"})
    finally:
        clear_db_override()
    assert resp.status_code == 400
    assert resp.json()["type"] == "/errors/validation"


async def test_create_rejects_duplicate_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "dup-p@example.com")
            r1 = await c.post("/api/v1/projects", json={"slug": "dup", "name": "A"})
            r2 = await c.post("/api/v1/projects", json={"slug": "dup", "name": "B"})
    finally:
        clear_db_override()
    assert r1.status_code == 201
    assert r2.status_code == 409


async def test_create_rejects_invalid_status(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "bad-status@example.com")
            resp = await c.post(
                "/api/v1/projects",
                json={"slug": "x", "name": "X", "status": "nonsense"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 422
