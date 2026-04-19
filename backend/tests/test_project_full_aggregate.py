import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_get_project_returns_full_aggregate(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "agg@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            await c.patch(
                "/api/v1/projects/pa/context",
                json={"current_focus": "focus"},
            )
            await c.post(
                "/api/v1/projects/pa/repos",
                json={"git_url": "git@example.com:x.git"},
            )
            await c.post(
                "/api/v1/projects/pa/stack",
                json={"stack_item_slug": "fastapi"},
            )
            await c.post(
                "/api/v1/projects/pa/tags",
                json={"name": "python"},
            )
            resp = await c.get("/api/v1/projects/pa")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["context"]["current_focus"] == "focus"
    assert len(body["repos"]) == 1
    assert body["repos"][0]["git_url"] == "git@example.com:x.git"
    assert len(body["stack"]) == 1
    assert body["stack"][0]["stack_item_slug"] == "fastapi"
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "python"
