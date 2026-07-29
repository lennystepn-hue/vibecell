"""User-scoped onboarding event bus.

The sibling of `services/events.py`, which is per-*project*. Onboarding has
no project yet — that is the whole point, the projects are about to be
created — so this one is keyed by user.

Two publishers will feed it, both landing in later sessions:

  * `hangar setup --code` (issue #5) reports MCP-client detection and config
    writes as they happen on the user's machine
  * the `vibecell_onboard` MCP tool (issue #6) reports repo scanning and
    per-project enrichment as the agent works

The browser consumes it over SSE while the onboarding screen narrates. Before
this existed the wizard polled `connections.refresh()` every 3 seconds and
could learn exactly one thing: whether the list had got longer.

Channel: vc:onboarding:{user_id}
Payload: {"type": "<event_type>", "user_id": "...", "at": "<iso>", ...extra}
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal, get_args

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

CHANNEL_TEMPL = "vc:onboarding:{user_id}"

# The complete vocabulary. Publishers in #5 and #6 must use one of these —
# `publish()` rejects anything else rather than emitting an event no client
# knows how to render. A silently-ignored event is worse than a loud failure
# here, because the symptom appears in the browser as "nothing happened".
OnboardingEvent = Literal[
    "stream.open",        # handshake, emitted by the endpoint itself
    "paired",             # {client}            — a device token was issued
    "client.configured",  # {client, ok, reason?} — one MCP client written
    "scan.started",       # {repo_count}
    "project.created",    # {slug, name}
    "project.enriched",   # {slug, pitch, stack}
    "done",               # {project_count}
]

EVENT_TYPES: frozenset[str] = frozenset(get_args(OnboardingEvent))


def _channel(user_id: str) -> str:
    return CHANNEL_TEMPL.format(user_id=user_id)


def build_frame(user_id: str, event_type: str, payload: dict[str, Any] | None = None) -> str:
    """Serialise one event. Split out so tests can assert shape without Redis."""
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"unknown onboarding event {event_type!r}; "
            f"add it to OnboardingEvent if it is real"
        )
    body: dict[str, Any] = {
        "type": event_type,
        "user_id": user_id,
        "at": datetime.now(UTC).isoformat(),
    }
    if payload:
        body.update(payload)
    return json.dumps(body)


async def publish(
    user_id: str,
    event_type: OnboardingEvent | str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish one onboarding event.

    Unlike `events.publish`, an unknown event type raises. Project events are
    fire-and-forget decoration on top of data the client can refetch; these
    ARE the client's only source of truth for what is happening on a machine
    it cannot see. A typo must not degrade into silence.

    Delivery itself stays best-effort: a Redis hiccup logs and moves on, since
    failing the caller would abort a working install over a cosmetic stream.
    """
    frame = build_frame(user_id, event_type, payload)
    try:
        r = await get_redis()
        await r.publish(_channel(user_id), frame)
    except Exception:
        logger.warning(
            "onboarding event publish failed (%s, %s)", user_id, event_type, exc_info=True
        )


async def subscribe(user_id: str):  # -> AsyncIterator[str]
    """Async iterator yielding JSON-encoded payloads for one user.

    Yields already-serialised JSON so the SSE endpoint can drop it straight
    into a `data:` frame. Caller must close the generator.
    """
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(user_id))
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
        await pubsub.unsubscribe(_channel(user_id))
        await pubsub.close()
