import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_context_get_returns_empty_before_upsert(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "ctx-empty@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            resp = await c.get("/api/v1/projects/pa/context")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_focus"] is None
    assert body["open_questions"] == []


async def test_context_patch_upserts(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "ctx-patch@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            resp = await c.patch(
                "/api/v1/projects/pa/context",
                json={
                    "current_focus": "Ship webhook",
                    "next_step": "Handle deletion",
                    "open_questions": ["Pro-rata?"],
                },
            )
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_focus"] == "Ship webhook"
    assert body["open_questions"] == ["Pro-rata?"]


async def test_context_404_when_project_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "ctx-404@example.com")
            resp = await c.get("/api/v1/projects/nope/context")
    finally:
        clear_db_override()
    assert resp.status_code == 404
