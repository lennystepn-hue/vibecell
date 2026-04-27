"""Tests for the public /api/v1/status endpoint (Spec-6 C4)."""
from __future__ import annotations

from httpx import AsyncClient


async def test_status_returns_payload(client: AsyncClient) -> None:
    """Status endpoint returns the documented shape and aggregates correctly."""
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()

    # Top-level shape
    assert body["overall"] in {"ok", "degraded", "down"}
    assert isinstance(body["components"], list)
    assert isinstance(body["incidents"], list)
    assert "version" in body
    assert "git_sha" in body
    assert "generated_at" in body

    # Each component obeys its sub-shape
    component_names = {c["name"] for c in body["components"]}
    assert {"API", "Database", "MCP", "Billing", "GitHub sync"} <= component_names

    for c in body["components"]:
        assert c["status"] in {"ok", "degraded", "down"}
        assert "latency_ms" in c
        assert "message" in c

    # API + Database probes should be healthy in the test environment
    by_name = {c["name"]: c for c in body["components"]}
    assert by_name["API"]["status"] == "ok"
    assert by_name["Database"]["status"] == "ok"


async def test_status_is_anonymous(client: AsyncClient) -> None:
    """No auth required — that's the entire point of a status page."""
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
