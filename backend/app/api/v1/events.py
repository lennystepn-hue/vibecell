"""Per-project Server-Sent Events stream — makes the dashboard feel live.

Clients connect to /api/v1/projects/{slug}/events/stream; the backend tails
the Redis pub/sub channel for that project and yields `data: {json}\\n\\n`
frames as events arrive. On each event the frontend refetches the store
backing the affected card (sessions, decisions, secrets, screenshots, …).
"""
from __future__ import annotations

import asyncio
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
    """Yield SSE frames: hello → live updates → periodic heartbeats."""
    # Opening handshake so the client knows the stream is live.
    hello = json.dumps({
        "type": "stream.open",
        "project_id": project_id,
        "at": datetime.now(UTC).isoformat(),
    })
    yield f"data: {hello}\n\n"

    sub = events_svc.subscribe(project_id)
    sub_task: asyncio.Task[str | None] = asyncio.create_task(sub.__anext__())  # type: ignore[arg-type]

    try:
        while True:
            done, _pending = await asyncio.wait(
                {sub_task}, timeout=HEARTBEAT_SECONDS,
            )
            if not done:
                # No events this interval — emit heartbeat so proxies don't close.
                yield ": heartbeat\n\n"
                continue
            try:
                payload = sub_task.result()
            except StopAsyncIteration:
                break
            if payload is None:
                break
            yield f"data: {payload}\n\n"
            sub_task = asyncio.create_task(sub.__anext__())  # type: ignore[arg-type]
    finally:
        sub_task.cancel()
        # Close underlying pubsub via generator teardown.
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
