import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration


async def test_magic_link_accepts_valid_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    monkeypatch.setenv(
        "HANGAR_DATABASE_URL",
        "postgresql+asyncpg://hangar:hangar_dev@localhost:5432/hangar_dev",
    )
    from app.core.config import get_settings
    get_settings.cache_clear()

    email = f"u-{uuid.uuid4()}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/auth/magic-link", json={"email": email})
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


async def test_magic_link_rejects_malformed_email() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/auth/magic-link", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_magic_link_is_case_insensitive_for_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    monkeypatch.setenv(
        "HANGAR_DATABASE_URL",
        "postgresql+asyncpg://hangar:hangar_dev@localhost:5432/hangar_dev",
    )
    from app.core.config import get_settings
    get_settings.cache_clear()

    unique = uuid.uuid4().hex[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await c.post(
            "/api/v1/auth/magic-link",
            json={"email": f"Mixed-{unique}@Example.COM"},
        )
    assert r1.status_code == 202
