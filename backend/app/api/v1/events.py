"""Per-project Server-Sent Events stream — makes the dashboard feel live.

Clients connect to /api/v1/projects/{slug}/events/stream; the backend tails
the Redis pub/sub channel for that project and yields `data: {json}\\n\\n`
frames as events arrive. On each event the frontend refetches the store
backing the affected card (sessions, decisions, secrets, screenshots, …).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.deps import ProjectContext, require_project
from app.services import events as events_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/events", tags=["events"])

# Heartbeat interval — keeps the HTTP connection alive through proxies that
# close idle streams. We send an SSE comment line (starts with ":") which the
# browser EventSource silently ignores.
HEARTBEAT_SECONDS = 20.0


async def _event_stream(project_id: str):  # -> AsyncIterator[str]
    """Yield SSE frames: hello → live updates → periodic heartbeats.

    Uses asyncio.wait_for on the async generator's __anext__ directly (no
    separate asyncio.Task) so that when the client disconnects the generator
    can be aclose()'d cleanly without the "asynchronous generator is already
    running" runtime error we hit on the first implementation.
    """
    # Opening handshake so the client knows the stream is live.
    hello = json.dumps({
        "type": "stream.open",
        "project_id": project_id,
        "at": datetime.now(UTC).isoformat(),
    })
    yield f"data: {hello}\n\n"

    sub = events_svc.subscribe(project_id)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(
                    sub.__anext__(),
                    timeout=HEARTBEAT_SECONDS,
                )
            except asyncio.TimeoutError:
                # No events this window — keep the socket alive for proxies.
                yield ": heartbeat\n\n"
                continue
            except StopAsyncIteration:
                break
            except asyncio.CancelledError:
                # Client disconnected mid-wait — bail out cleanly.
                break

            if payload is None:
                break
            yield f"data: {payload}\n\n"
    finally:
        # Suppress the "generator already running" race: if the client cut us
        # while __anext__ was still pending, aclose() inside the same frame
        # raises RuntimeError. Swallow it — there's nothing meaningful to do.
        with contextlib.suppress(RuntimeError, Exception):
            await sub.aclose()  # type: ignore[attr-defined]


@router.get("/stream")
async def stream(
    ctx: Annotated[ProjectContext, Depends(require_project)],
) -> StreamingResponse:
    """Open the SSE stream for this project."""
    return StreamingResponse(
        _event_stream(ctx.project.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx: don't buffer
        },
    )
