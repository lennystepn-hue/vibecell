from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.services.connections import ConnectionsService

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


@router.get("")
async def list_connections(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    svc = ConnectionsService(db)
    return await svc.list_for_user(user_id=auth.user.id)


@router.delete("/{connection_id}", status_code=204)
async def revoke_connection(
    connection_id: str,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str = Query(...),
) -> Response:
    if kind not in ("oauth", "cli"):
        raise HTTPException(400, "invalid_kind")
    svc = ConnectionsService(db)
    await svc.revoke(kind, connection_id)
    await db.commit()
    return Response(status_code=204)
