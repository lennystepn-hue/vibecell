"""Integration tests for POST /oauth/register (RFC 7591 Dynamic Client Registration).

Note: Rate-limit tests omitted for Phase 1 — will add once a rate-limit helper
is wired into the endpoint (Spec X).  The rate_limit.py module already exists
(app/core/rate_limit.py) but the register endpoint does not call it yet.
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
    """11th request from the same IP within the burst window should 429."""
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
                assert resp.status_code == 201
            resp = await client.post(
                "/oauth/register",
                json={
                    "client_name": "c11",
                    "redirect_uris": ["http://127.0.0.1:1/cb"],
                },
            )
            assert resp.status_code == 429
    finally:
        clear_db_override()
