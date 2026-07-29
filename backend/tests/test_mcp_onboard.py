"""The vibecell_onboard tool (issue #6).

Two modes on one tool: no arguments fetches the routine, an `event` reports
one step of it. The tests here pin the contract the agent depends on and the
boundary between what the agent may report and what it may not.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.mcp.auth import MCPContext
from app.mcp.handlers import onboard
from app.mcp.tools import TOOLS_BY_NAME, OnboardArgs
from app.services import onboarding_events as bus


def _Ctx(*, user_id: str) -> MCPContext:
    """Stand-in for MCPContext.

    The handler reads `user_id` and nothing else, so building a real context
    would mean conjuring a database session for a test that never touches
    one. The cast says that out loud rather than hiding behind a `type:
    ignore` at each call site.
    """
    return cast(MCPContext, SimpleNamespace(user_id=user_id))


# ── Registration ──────────────────────────────────────────────────────────


def test_tool_is_registered_under_the_underscore_name() -> None:
    assert "vibecell_onboard" in TOOLS_BY_NAME


def test_description_tells_the_agent_when_not_to_use_it() -> None:
    """A returning user must not get their disk re-scanned.

    The description is the only thing standing between "first-time setup" and
    "every session", so the negative case has to be in it.
    """
    desc = TOOLS_BY_NAME["vibecell_onboard"].description
    assert "first-time setup" in desc
    assert "vibecell_active" in desc


# ── Mode 1: the routine ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_arguments_returns_the_routine() -> None:
    out = await onboard.handle_onboard(OnboardArgs(), _Ctx(user_id="u_1"))
    assert "Vibecell onboarding" in out
    # The four things the routine must actually tell the agent to do.
    assert "scan.started" in out
    assert "vibecell_create_project" in out
    assert "vibecell_set_focus" in out
    assert 'event="done"' in out


@pytest.mark.asyncio
async def test_routine_forbids_inventing_data() -> None:
    """A single fabricated pitch costs trust in the whole portfolio."""
    out = await onboard.handle_onboard(OnboardArgs(), _Ctx(user_id="u_1"))
    assert "Never invent data" in out


@pytest.mark.asyncio
async def test_routine_tells_the_agent_to_report_as_it_goes() -> None:
    # Batching at the end would leave the user watching a blank screen for a
    # minute and then everything at once — the opposite of the point.
    out = await onboard.handle_onboard(OnboardArgs(), _Ctx(user_id="u_1"))
    assert "not in a batch at the end" in out


# ── Mode 2: reporting ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reporting_publishes_to_the_users_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str, dict | None]] = []

    async def fake_publish(user_id, event_type, payload=None):
        seen.append((user_id, event_type, payload))

    monkeypatch.setattr(bus, "publish", fake_publish)

    await onboard.handle_onboard(
        OnboardArgs(event="project.created", slug="butlr", name="Butlr"),
        _Ctx(user_id="u_42"),
    )
    assert seen == [("u_42", "project.created", {"slug": "butlr", "name": "Butlr"})]


@pytest.mark.asyncio
async def test_reporting_drops_unset_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """`scan.started` carries a count and nothing else.

    Sending nulls for the other six would make every frame carry the union of
    all payloads and force the client to filter them back out.
    """
    seen: list[dict | None] = []

    async def fake_publish(user_id, event_type, payload=None):
        seen.append(payload)

    monkeypatch.setattr(bus, "publish", fake_publish)

    await onboard.handle_onboard(
        OnboardArgs(event="scan.started", repo_count=14), _Ctx(user_id="u_1")
    )
    assert seen == [{"repo_count": 14}]


@pytest.mark.asyncio
async def test_done_acknowledges_with_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_publish(*a, **k):
        return None

    monkeypatch.setattr(bus, "publish", fake_publish)

    out = await onboard.handle_onboard(
        OnboardArgs(event="done", project_count=12), _Ctx(user_id="u_1")
    )
    assert "12" in out


def test_agent_cannot_report_events_that_are_not_its_to_report() -> None:
    """`paired` belongs to the installer, `stream.open` to the endpoint.

    Both are in the bus vocabulary; neither is in this tool's Literal. If the
    two ever drift apart, this fails.
    """
    import pydantic

    for forbidden in ("paired", "stream.open"):
        with pytest.raises(pydantic.ValidationError):
            OnboardArgs(event=forbidden)  # type: ignore[arg-type]


def test_every_event_the_tool_accepts_is_known_to_the_bus() -> None:
    """The other direction: nothing the agent can send is unroutable."""
    accepted = {"scan.started", "project.created", "project.enriched", "done"}
    assert accepted <= bus.EVENT_TYPES
