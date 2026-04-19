import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_infra_upsert(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "infra@example.com")
            await c.post("/api/v1/projects", json={"slug": "pa", "name": "P"})
            r1 = await c.patch(
                "/api/v1/projects/pa/infra",
                json={"server_alias": "prod", "domain_primary": "example.com"},
            )
            assert r1.status_code == 200
            assert r1.json()["server_alias"] == "prod"

            # Second patch updates only domains
            r2 = await c.patch(
                "/api/v1/projects/pa/infra",
                json={"domains": ["example.com", "example.io"]},
            )
    finally:
        clear_db_override()
    assert r2.status_code == 200
    body = r2.json()
    assert body["server_alias"] == "prod"  # preserved
    assert body["domains"] == ["example.com", "example.io"]
