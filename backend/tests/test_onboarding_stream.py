"""Onboarding event bus + user-scoped SSE stream (issue #3).

The stream is the only thing standing between the user and a blank screen
while `hangar setup` and `vibecell_onboard` work on a machine the browser
cannot see. These tests pin the two properties that actually matter: the
vocabulary is closed, and one user's frames never reach another user.
"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.services import onboarding_events as bus

# ── Vocabulary ────────────────────────────────────────────────────────────


def test_build_frame_shapes_the_payload() -> None:
    frame = json.loads(bus.build_frame("u_1", "project.created", {"slug": "butlr", "name": "Butlr"}))
    assert frame["type"] == "project.created"
    assert frame["user_id"] == "u_1"
    assert frame["slug"] == "butlr"
    assert frame["name"] == "Butlr"
    assert frame["at"]  # ISO timestamp present


def test_build_frame_rejects_an_invented_event_type() -> None:
    # The failure mode this guards: a publisher in #5/#6 emits
    # "project.enrich" (no 'ed'), the client never renders it, and the symptom
    # is a screen that just sits there. Fail loudly at the source instead.
    with pytest.raises(ValueError, match="unknown onboarding event"):
        bus.build_frame("u_1", "project.enrich")


def test_every_documented_event_type_is_accepted() -> None:
    for event_type in [
        "stream.open",
        "paired",
        "client.configured",
        "scan.started",
        "project.created",
        "project.enriched",
        "done",
    ]:
        assert json.loads(bus.build_frame("u_1", event_type))["type"] == event_type


def test_channel_is_per_user() -> None:
    assert bus._channel("u_1") != bus._channel("u_2")
    assert "u_1" in bus._channel("u_1")


# ── Endpoint ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/onboarding/stream")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dev_publish_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/api/v1/onboarding/_publish", json={"type": "done"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dev_publish_rejects_unknown_event_type(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "dev_mode", True, raising=False)

    r = await authed_client.post(
        "/api/v1/onboarding/_publish",
        json={"type": "totally.made.up"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_report_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/api/v1/onboarding/report", json={"type": "paired"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_report_accepts_what_an_installer_knows(authed_client: AsyncClient) -> None:
    for body in (
        {"type": "paired"},
        {"type": "client.configured", "client": "cursor", "ok": True},
        {"type": "client.configured", "client": "zed", "ok": False, "reason": "not found"},
    ):
        r = await authed_client.post("/api/v1/onboarding/report", json=body)
        assert r.status_code == 204, body


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["done", "project.created", "scan.started"])
async def test_report_refuses_events_the_installer_cannot_know(
    authed_client: AsyncClient, event_type: str
) -> None:
    """The installer wires up MCP clients. It knows nothing about repos.

    Those events come from the agent in #6, over a different credential. A
    device token that could fake `done` could make the onboarding screen
    declare victory over an install that never happened.
    """
    r = await authed_client.post("/api/v1/onboarding/report", json={"type": event_type})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_dev_publish_requires_a_type(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "dev_mode", True, raising=False)

    r = await authed_client.post("/api/v1/onboarding/_publish", json={"slug": "butlr"})
    assert r.status_code == 422
