import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_stack_items_list_returns_seeded_entries(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-list@example.com")
            # >40 seeded items and default limit is 50; request the max to cover
            # slugs at both ends of the alphabet ("fastapi" early, "vue" late).
            resp = await c.get("/api/v1/stack-items?limit=200")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    slugs = {i["slug"] for i in body}
    assert "fastapi" in slugs
    assert "vue" in slugs


async def test_stack_items_filter_by_q(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-q@example.com")
            resp = await c.get("/api/v1/stack-items?q=clau")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()}
    assert "claude" in slugs


async def test_stack_items_filter_by_kind(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-kind@example.com")
            resp = await c.get("/api/v1/stack-items?kind=model")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    kinds = {i["kind"] for i in resp.json()}
    assert kinds == {"model"}


async def test_stack_items_create_custom(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-create@example.com")
            resp = await c.post(
                "/api/v1/stack-items",
                json={"slug": "my-custom-tool", "name": "My Custom Tool", "kind": "service"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 201
    assert resp.json()["slug"] == "my-custom-tool"


async def test_stack_items_create_rejects_duplicate(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-dup@example.com")
            resp = await c.post(
                "/api/v1/stack-items",
                json={"slug": "fastapi", "name": "FastAPI"},  # already seeded
            )
    finally:
        clear_db_override()
    assert resp.status_code == 409
