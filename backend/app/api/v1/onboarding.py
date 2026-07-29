"""User-scoped onboarding SSE stream.

The browser opens `/api/v1/onboarding/stream` when the onboarding screen
mounts and keeps it open while the agent works. Everything the user sees on
that screen — "gekoppelt", "14 Repos gefunden", "butlr wird gelesen" — is a
frame from here.

Construction deliberately mirrors `api/v1/events.py` (per-project stream):
same heartbeat handling, same generator-close dance, same proxy headers. Two
streams that behave differently under a flaky connection would be two bugs to
find instead of one.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import HangarError, RateLimitedError
from app.core.rate_limit import check_and_consume
from app.services import onboarding_events as bus
from app.services import onboarding_pair as pair_svc

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

# `/i/{code}` deliberately sits at the root rather than under /api/v1: it goes
# inside a `curl … | sh` one-liner that a user reads off a screen, and every
# character there is one more chance to mistype.
install_router = APIRouter(tags=["onboarding"])

_DbDep = Annotated[AsyncSession, Depends(get_db)]

# Matches the per-project stream. Proxies that close idle connections need to
# see traffic; an SSE comment line is ignored by EventSource.
HEARTBEAT_SECONDS = 20.0


async def _event_stream(user_id: str):  # -> AsyncIterator[str]
    """Yield SSE frames: hello → live updates → periodic heartbeats."""
    yield f"data: {bus.build_frame(user_id, 'stream.open')}\n\n"

    sub = bus.subscribe(user_id)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(
                    sub.__anext__(),
                    timeout=HEARTBEAT_SECONDS,
                )
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            except StopAsyncIteration:
                break
            except asyncio.CancelledError:
                # Client disconnected mid-wait.
                break

            if payload is None:
                break
            yield f"data: {payload}\n\n"
    finally:
        # If the client cut us while __anext__ was still pending, aclose() in
        # the same frame raises RuntimeError. Nothing useful to do about it.
        with contextlib.suppress(RuntimeError, Exception):
            await sub.aclose()


@router.get("/stream")
async def stream(
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> StreamingResponse:
    """Open the onboarding stream for the signed-in user.

    Scoped to `auth.user.id`, so a user can only ever watch their own machine
    being set up.
    """
    return StreamingResponse(
        _event_stream(auth.user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx: don't buffer
        },
    )


class CodeOut(BaseModel):
    """A freshly minted pairing code plus the exact lines to show the user."""

    code: str
    expires_in: int
    install_sh: str
    install_ps1: str


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=64)
    device_name: str | None = Field(default=None, max_length=120)


class RedeemResponse(BaseModel):
    token: str
    device_id: str
    user_id: str
    workspace_id: str
    workspace_slug: str


@router.post("/code", response_model=CodeOut)
async def mint_code(auth: Annotated[AuthContext, Depends(require_auth)]) -> CodeOut:
    """Mint a one-time pairing code for the signed-in user.

    The onboarding screen calls this on mount and again a little before
    expiry, so the line on screen is never dead. Reissue is a plain re-call
    rather than a push down the SSE stream — that stream carries progress
    *from* the user's machine, and mixing control-plane traffic into it would
    make both harder to reason about.
    """
    code, ttl = await pair_svc.issue_code(
        user_id=auth.user.id, workspace_id=auth.active_workspace_id
    )
    base = get_settings().base_url.rstrip("/")
    return CodeOut(
        code=code,
        expires_in=ttl,
        install_sh=f"curl -LsSf {base}/i/{code} | sh",
        install_ps1=f"irm {base}/i/{code} | iex",
    )


@router.post("/redeem", response_model=RedeemResponse)
async def redeem(request: Request, body: RedeemRequest, db: _DbDep) -> RedeemResponse:
    """Spend a pairing code for a device token. Called by the installer.

    Anonymous by necessity — the whole point is that the machine running the
    one-liner has no session. The code is the credential, it is single-use,
    and it can only ever produce a device.
    """
    ip = request.client.host if request.client else "unknown"
    allowed, retry = await check_and_consume(
        f"rl:onboarding-redeem:{ip}", capacity=20, refill_rate=20 / 3600
    )
    if not allowed:
        raise RateLimitedError(detail="too many redeem attempts", retry_after_s=retry)

    result = await pair_svc.redeem_code(
        db, code=body.code, device_name=body.device_name
    )
    await db.commit()

    # Tell the browser the machine is paired — this is the first frame the
    # onboarding screen gets that proves the one-liner actually ran.
    await bus.publish(
        result["user_id"], "paired", {"client": body.device_name or "cli"}
    )
    return RedeemResponse(**result)


class ReportRequest(BaseModel):
    """One progress line from the installer running on the user's machine."""

    type: str
    client: str | None = None
    ok: bool | None = None
    reason: str | None = None


# What `hangar setup` is allowed to say. Deliberately narrower than the full
# vocabulary: the installer knows about pairing and MCP clients, and nothing
# about repos or projects. Those come from the agent in #6, over a different
# credential. A device token that could fake `done` could make the onboarding
# screen declare victory over an install that never happened.
_INSTALLER_EVENTS = frozenset({"paired", "client.configured"})


@router.post("/report", status_code=204)
async def report(
    auth: Annotated[AuthContext, Depends(require_auth)],
    body: ReportRequest,
) -> None:
    """Progress from the installer. Authenticated by the device bearer token.

    The token was minted seconds earlier by `/redeem`, so this is the same
    machine reporting on work the user just asked for.
    """
    if body.type not in _INSTALLER_EVENTS:
        raise HangarError(
            title="Event not reportable by an installer",
            status=422,
            type_="/errors/validation",
            detail=f"{body.type!r} is not one of {sorted(_INSTALLER_EVENTS)}",
        )
    payload = body.model_dump(exclude_none=True, exclude={"type"})
    await bus.publish(auth.user.id, body.type, payload or None)


_SHIM_SH = """\
#!/usr/bin/env sh
# Vibecell one-line setup. Carries your pairing code to the installer.
set -eu
HANGAR_SETUP_CODE={code}
export HANGAR_SETUP_CODE
curl -LsSf {base}/install.sh | sh
"""

_SHIM_PS1 = """\
# Vibecell one-line setup. Carries your pairing code to the installer.
$ErrorActionPreference = "Stop"
$env:HANGAR_SETUP_CODE = "{code}"
irm {base}/install.ps1 | iex
"""

_DEAD_SH = """\
#!/usr/bin/env sh
echo "This Vibecell setup link has expired or was already used." >&2
echo "Open {base}/welcome and copy a fresh line." >&2
exit 1
"""

_DEAD_PS1 = """\
Write-Error "This Vibecell setup link has expired or was already used."
Write-Error "Open {base}/welcome and copy a fresh line."
exit 1
"""


def _wants_powershell(user_agent: str) -> bool:
    """PowerShell's `irm` identifies itself; curl and wget do not."""
    ua = user_agent.lower()
    return "powershell" in ua or "windowspowershell" in ua


@install_router.get("/i/{code}", response_class=PlainTextResponse)
async def install_script(code: str, request: Request) -> PlainTextResponse:
    """Serve the setup one-liner with the pairing code baked in.

    Returns a thin shim rather than the installer itself: the real
    `install.sh` / `install.ps1` stay the single source of truth for how the
    binary gets onto a machine, and this only carries the code to them. One
    installer to keep correct, not three.

    A dead code still returns 200 with a script that explains itself — a
    404 body piped into `sh` produces a confusing parse error rather than a
    message anyone can act on.
    """
    base = get_settings().base_url.rstrip("/")
    ps = _wants_powershell(request.headers.get("user-agent", ""))
    alive = await pair_svc.code_exists(code)

    if not alive:
        body = (_DEAD_PS1 if ps else _DEAD_SH).format(base=base)
    else:
        body = (_SHIM_PS1 if ps else _SHIM_SH).format(code=code, base=base)

    return PlainTextResponse(
        body,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/_publish", status_code=204)
async def publish_for_dev(
    auth: Annotated[AuthContext, Depends(require_auth)],
    body: Annotated[dict[str, Any], Body()],
) -> None:
    """Publish an event to your own stream. Dev mode only.

    Exists so the stream and the frontend store can be exercised end to end
    before the real publishers land in #5 and #6. Gated on dev mode and hard
    scoped to the caller's own channel — it takes no user id, so it cannot be
    aimed at anyone else even if it were somehow reachable in production.
    """
    if not get_settings().dev_mode:
        raise HangarError(
            title="Dev endpoint disabled",
            status=404,
            type_="/errors/not-found",
            detail="dev mode not enabled",
        )
    event_type = body.get("type")
    if not isinstance(event_type, str):
        raise HangarError(
            title="Missing event type",
            status=422,
            type_="/errors/validation",
            detail="body must include a string `type`",
        )
    payload = {k: v for k, v in body.items() if k != "type"}
    try:
        await bus.publish(auth.user.id, event_type, payload or None)
    except ValueError as exc:
        raise HangarError(
            title="Unknown event type",
            status=422,
            type_="/errors/validation",
            detail=str(exc),
        ) from exc
