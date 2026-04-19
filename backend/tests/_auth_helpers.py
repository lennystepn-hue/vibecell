"""Shared helpers for auth-gated integration tests."""
from collections.abc import AsyncIterator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.services.login import issue_magic_link


def override_db(session: AsyncSession) -> None:
    async def _fake_get_db() -> AsyncIterator[AsyncSession]:
        yield session
    app.dependency_overrides[get_db] = _fake_get_db


def clear_db_override() -> None:
    app.dependency_overrides.pop(get_db, None)


async def sign_in(c: AsyncClient, session: AsyncSession, email: str) -> None:
    raw = await issue_magic_link(session, email=email)
    await session.flush()
    r = await c.get(f"/api/v1/auth/verify?token={raw}")
    assert r.status_code == 303, f"sign-in failed: {r.status_code} {r.text}"
