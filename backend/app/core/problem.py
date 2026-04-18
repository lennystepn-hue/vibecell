"""Map HangarError → RFC 7807 Problem+JSON response."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import HangarError, RateLimitedError


async def _hangar_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HangarError):
        # Defensive: the handler is only registered for HangarError, but if
        # a subclass chain breaks or someone mis-registers it, surface 500
        # with a safe generic Problem rather than returning an empty 200.
        return JSONResponse(
            status_code=500,
            content={
                "type": "/errors/internal",
                "title": "Internal Server Error",
                "status": 500,
            },
            media_type="application/problem+json",
        )
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.extras.get("retry_after_s", 0))
    return JSONResponse(
        status_code=exc.status,
        content=exc.to_problem(),
        headers=headers,
        media_type="application/problem+json",
    )


def install_problem_handler(app: FastAPI) -> None:
    app.add_exception_handler(HangarError, _hangar_error_handler)
