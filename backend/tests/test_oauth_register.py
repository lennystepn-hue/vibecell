"""Integration tests for POST /oauth/register (RFC 7591 Dynamic Client Registration).

Rate-limit is wired in `app/oauth/server.py::register` (capacity=10, refill=10/min
per source IP). The rate-limit test below explicitly drains the bucket via Redis
before the run and cleans up after, so it doesn't pollute sibling tests that hit
the same endpoint with the default ASGITransport client IP.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db

pytestmark = pytest.mark.integration


async def test_register_happy_path(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            resp = await client.post(
                "/oauth/register",
                json={
                    "client_name": "Claude Desktop",
                    "redirect_uris": ["http://127.0.0.1:12345/callback"],
                    "scope": "vibecell:tools",
                },
            )
    finally:
        clear_db_override()
    assert resp.status_code == 201
    body = resp.json()
    assert body["client_id"].startswith("dyn_")
    assert body["client_name"] == "Claude Desktop"
    assert body["redirect_uris"] == ["http://127.0.0.1:12345/callback"]
    assert body["token_endpoint_auth_method"] == "none"
    assert isinstance(body["client_id_issued_at"], int)


async def test_register_rejects_http_non_loopback(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            resp = await client.post(
                "/oauth/register",
                json={
                    "client_name": "Sketchy",
                    "redirect_uris": ["http://evil.com/cb"],
                    "scope": "vibecell:tools",
                },
            )
    finally:
        clear_db_override()
    assert resp.status_code == 422


async def test_register_accepts_https(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            resp = await client.post(
                "/oauth/register",
                json={
                    "client_name": "Web",
                    "redirect_uris": ["https://app.example.com/cb"],
                    "scope": "vibecell:tools",
                },
            )
    finally:
        clear_db_override()
    assert resp.status_code == 201


async def test_register_rate_limit(session: AsyncSession) -> None:
    """11th request from the same IP within the burst window should 429.

    The endpoint uses `app.core.rate_limit.check_and_consume` keyed on
    `oauth:register:{client_ip}`. ASGITransport defaults the client IP to
    "127.0.0.1", so we reset that bucket before draining it and clean up
    after to keep the test idempotent across runs and isolated from siblings.
    """
    from app.core.redis import get_redis

    redis = await get_redis()
    bucket_key = "oauth:register:127.0.0.1"
    await redis.delete(bucket_key)

    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            for i in range(10):
                resp = await client.post(
                    "/oauth/register",
                    json={
                        "client_name": f"c{i}",
                        "redirect_uris": ["http://127.0.0.1:1/cb"],
                    },
                )
                assert resp.status_code == 201, f"req {i} failed: {resp.text}"
            resp = await client.post(
                "/oauth/register",
                json={
                    "client_name": "c11",
                    "redirect_uris": ["http://127.0.0.1:1/cb"],
                },
            )
            assert resp.status_code == 429
            assert resp.json()["detail"]["error"] == "rate_limited"
            assert resp.headers.get("Retry-After") is not None
    finally:
        clear_db_override()
        await redis.delete(bucket_key)
