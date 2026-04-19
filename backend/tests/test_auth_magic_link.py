import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(autouse=True)
async def _flush_auth_rate_limits() -> None:
    """Clear `rl:auth:*` Redis keys before each test so per-IP/per-email
    buckets accumulated in one test don't 429 the next one."""
    from app.core.redis import get_redis
    redis = await get_redis()
    async for key in redis.scan_iter(match="rl:auth:*"):
        await redis.delete(key)


def _override_db(session: AsyncSession) -> None:
    async def _fake_get_db() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db] = _fake_get_db


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_db, None)


async def test_magic_link_accepts_valid_email(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    email = f"u-{uuid.uuid4()}@example.com"
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.post("/api/v1/auth/magic-link", json={"email": email})
    finally:
        _clear_db_override()
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


async def test_magic_link_rejects_malformed_email() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/auth/magic-link", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_magic_link_is_case_insensitive_for_email(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    unique = uuid.uuid4().hex[:8]
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.post(
                "/api/v1/auth/magic-link",
                json={"email": f"Mixed-{unique}@Example.COM"},
            )
    finally:
        _clear_db_override()
    assert r1.status_code == 202
