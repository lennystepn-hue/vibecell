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

from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.deps import AuthContext, require_auth
from app.core.errors import HangarError
from app.services import onboarding_events as bus

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

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
