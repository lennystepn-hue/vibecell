"""FastAPI middleware: session cookie → request.state + audit contextvars."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.audit import current_actor, current_workspace_id
from app.core.config import get_settings
from app.core.session import get_session

if TYPE_CHECKING:
    from fastapi import FastAPI

SESSION_COOKIE_NAME = "hangar_session"


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        actor_token = None
        workspace_token = None

        if session_id:
            payload = await get_session(session_id)
            if payload is not None:
                request.state.user_id = payload.user_id
                request.state.workspace_id = payload.workspace_id
                actor_token = current_actor.set(f"ui:{payload.user_id}")
                workspace_token = current_workspace_id.set(payload.workspace_id)

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
