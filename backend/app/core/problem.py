"""Map HangarError → RFC 7807 Problem+JSON response."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import HangarError, RateLimitedError


async def _hangar_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HangarError)
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
