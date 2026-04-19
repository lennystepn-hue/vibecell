"""FastAPI middleware: session cookie or bearer token → request.state + audit contextvars."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.audit import current_actor, current_workspace_id
from app.core.config import get_settings
from app.core.session import get_session

if TYPE_CHECKING:
    from fastapi import FastAPI

SESSION_COOKIE_NAME = "hangar_session"


async def _resolve_bearer(request: Request) -> tuple[str, str, str] | None:
    """Return (user_id, workspace_id, device_id) if `Authorization: Bearer …` resolves.

    Looks up cli_devices by sha256(token). The bound workspace is the user's
    first-owned workspace (matches magic-link first-login bootstrap).
    Fire-and-forget updates last_seen_at on the device row.
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    raw_token = auth_header.split(" ", 1)[1].strip()
    if not raw_token:
        return None

    # Local imports to avoid circular import at module load.
    from app.core.db import session_scope
    from app.models import Workspace
    from app.services.cli_pair import find_device_by_token

    async with session_scope() as db:
        device = await find_device_by_token(db, raw_token=raw_token)
        if device is None:
            return None

        ws = (await db.execute(
            select(Workspace).where(Workspace.owner_id == device.user_id).limit(1)
        )).scalar_one_or_none()
        if ws is None:
            return None

        # Touch last_seen_at (commits on scope exit).
        from datetime import UTC, datetime
        device.last_seen_at = datetime.now(UTC)

        return device.user_id, ws.id, device.id


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        actor_token = None
        workspace_token = None
        user_id: str | None = None
        workspace_id: str | None = None

        if session_id:
            payload = await get_session(session_id)
            if payload is not None:
                user_id = payload.user_id
                workspace_id = payload.workspace_id
                request.state.user_id = user_id
                request.state.workspace_id = workspace_id
                actor_token = current_actor.set(f"ui:{user_id}")
                workspace_token = current_workspace_id.set(workspace_id)

        # Fallback to bearer token only when no cookie session was resolved.
        if user_id is None:
            resolved = await _resolve_bearer(request)
            if resolved is not None:
                user_id, workspace_id, device_id = resolved
                request.state.user_id = user_id
                request.state.workspace_id = workspace_id
                request.state.device_id = device_id
                actor_token = current_actor.set(f"cli:{device_id}")
                workspace_token = current_workspace_id.set(workspace_id)

        try:
            return await call_next(request)
        finally:
            if actor_token is not None:
                current_actor.reset(actor_token)
            if workspace_token is not None:
                current_workspace_id.reset(workspace_token)


def install_session_middleware(app: FastAPI) -> None:
    app.add_middleware(SessionMiddleware)


def session_cookie_attrs() -> dict[str, object]:
    s = get_settings()
    return {
        "key": SESSION_COOKIE_NAME,
        "max_age": s.session_max_age,
        "httponly": True,
        "secure": not s.dev_mode,
        "samesite": "lax",
        "domain": s.cookie_domain if s.cookie_domain != "localhost" else None,
        "path": "/",
    }
