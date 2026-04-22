"""Redis-backed project event bus.

Every write that a project card cares about (session created, decision
recorded, secret used, ship fired, screenshot captured, idea captured, note
saved, todo completed, …) publishes a small JSON payload to a per-project
Redis pub/sub channel. The SSE endpoint subscribes and streams to the
browser; the frontend refetches the affected store on each event.

Keeps cards feeling **live** — no manual reload, no aggressive polling.

Channel: vc:project_events:{project_id}
Payload: {"type": "<event_type>", "project_id": "...", "at": "<iso>", ...extra}
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

CHANNEL_TEMPL = "vc:project_events:{project_id}"


def _channel(project_id: str) -> str:
    return CHANNEL_TEMPL.format(project_id=project_id)


async def publish(
    project_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget publish. Never raises — event delivery is best-effort."""
    try:
        r = await get_redis()
        body = {
            "type": event_type,
            "project_id": project_id,
            "at": datetime.now(UTC).isoformat(),
        }
        if payload:
            body.update(payload)
        await r.publish(_channel(project_id), json.dumps(body))
    except Exception:  # noqa: BLE001
        logger.warning("event publish failed (%s, %s)", project_id, event_type, exc_info=True)


async def subscribe(project_id: str):  # -> AsyncIterator[str]
    """Async iterator yielding JSON-encoded payloads for a project.

    Yields strings (already serialised JSON) so the SSE endpoint can feed
    them directly into its `data:` frame. Caller must close the generator.
    """
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(project_id))
    try:
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if isinstance(data, str):
                yield data
    finally:
        await pubsub.unsubscribe(_channel(project_id))
        await pubsub.close()
