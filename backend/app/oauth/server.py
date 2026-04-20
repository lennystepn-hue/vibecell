"""OAuth 2.1 authorization-server endpoints.

Phase 1 scope: POST /oauth/register (DCR per RFC 7591).
Tasks 1.8-1.10 append /authorize, /grant, /deny, /token, /revoke.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rate_limit import check_and_consume
from app.core.ulid import new_ulid
from app.oauth.models import OAuthClient
from app.oauth.schemas import RegisterRequest, RegisterResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await check_and_consume(
        f"oauth:register:{client_ip}",
        capacity=10,
        refill_rate=10 / 60,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    now = datetime.now(timezone.utc)
    client_id = "dyn_" + secrets.token_urlsafe(16)
    row = OAuthClient(
        id=new_ulid(),
        client_id=client_id,
        client_name=body.client_name,
        redirect_uris=body.redirect_uris,
        scope=body.scope,
        created_at=now,
    )
    db.add(row)
    await db.flush()

    return RegisterResponse(
        client_id=client_id,
        client_id_issued_at=int(now.timestamp()),
        client_name=body.client_name,
        redirect_uris=body.redirect_uris,
        scope=body.scope,
    )
