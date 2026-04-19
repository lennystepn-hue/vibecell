"""CLI device-code pairing endpoints (Spec 3 §4.2)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import RateLimitedError
from app.core.rate_limit import check_and_consume
from app.schemas.cli import (
    DeviceOut,
    PairCompleteRequest,
    PairCompleteResponse,
    PairConfirmRequest,
    PairStartResponse,
)
from app.services import cli_pair as cli_pair_svc

router = APIRouter(prefix="/api/v1/cli", tags=["cli"])

_DbDep = Annotated[AsyncSession, Depends(get_db)]
_AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.post("/pair/start", response_model=PairStartResponse)
async def pair_start(request: Request) -> PairStartResponse:
    """Anonymous — CLI calls this to obtain a device_code + user_code.

    Rate-limited per IP (10/hour) to prevent code-farming.
    """
    ip = request.client.host if request.client else "unknown"
    allowed, retry = await check_and_consume(
        f"rl:cli-pair:{ip}", capacity=10, refill_rate=10 / 3600
    )
    if not allowed:
        raise RateLimitedError(detail="too many pair starts", retry_after_s=retry)
    return await cli_pair_svc.start_pairing()


@router.post(
    "/pair/complete",
    # No response_model — returns either 200 with PairCompleteResponse or 202 pending.
    responses={
        200: {"model": PairCompleteResponse},
        202: {"description": "pairing pending — user has not confirmed yet"},
    },
)
async def pair_complete(body: PairCompleteRequest) -> JSONResponse:
    """Polling endpoint for the CLI. Returns 202 while pending, 200 with bearer token when ready."""
    result = await cli_pair_svc.complete_pairing(body.device_code)
    if result is None:
        return JSONResponse(status_code=202, content={"status": "pending"})
    return JSONResponse(status_code=200, content=result.model_dump())


@router.post("/pair/confirm", status_code=204)
async def pair_confirm(
    body: PairConfirmRequest,
    auth: _AuthDep,
    db: _DbDep,
) -> None:
    """Browser-side confirm: signed-in user submits the code from their terminal."""
    await cli_pair_svc.confirm_pairing(
        db,
        user_id=auth.user.id,
        workspace_id=auth.active_workspace_id,
        user_code=body.user_code,
        device_name=body.device_name,
    )
    await db.commit()


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(auth: _AuthDep, db: _DbDep) -> list[DeviceOut]:
    rows = await cli_pair_svc.list_devices(db, user_id=auth.user.id)
    return [
        DeviceOut(
            id=r.id,
            name=r.name,
            paired_at=r.paired_at.isoformat(),
            last_seen_at=r.last_seen_at.isoformat() if r.last_seen_at else None,
        )
        for r in rows
    ]


@router.delete("/devices/{device_id}", status_code=204)
async def revoke_device(device_id: str, auth: _AuthDep, db: _DbDep) -> None:
    await cli_pair_svc.revoke_device(db, user_id=auth.user.id, device_id=device_id)
    await db.commit()
