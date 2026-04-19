import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_repo_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "repos@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r_create = await c.post(
                "/api/v1/projects/pa/repos",
                json={"role": "monorepo", "git_url": "git@github.com:x/y.git", "primary_lang": "Python"},
            )
            assert r_create.status_code == 201
            repo_id = r_create.json()["id"]

            r_patch = await c.patch(
                f"/api/v1/projects/pa/repos/{repo_id}",
                json={"default_branch": "main"},
            )
            assert r_patch.status_code == 200
            assert r_patch.json()["default_branch"] == "main"

            r_del = await c.delete(f"/api/v1/projects/pa/repos/{repo_id}")
            assert r_del.status_code == 204

            r_del2 = await c.delete(f"/api/v1/projects/pa/repos/{repo_id}")
            assert r_del2.status_code == 404
    finally:
        clear_db_override()
