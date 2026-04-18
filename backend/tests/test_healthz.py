# backend/tests/test_healthz.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "version" in body
