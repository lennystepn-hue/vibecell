"""/api/v1/search — workspace-scoped FTS federation."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.services import search as search_svc

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get("/search")
async def search(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    entity: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    hits = await search_svc.union_search(
        db,
        workspace_id=auth.active_workspace_id,
        query=q,
        limit=limit,
        entity_filter=entity,
    )
    return [h.to_dict() for h in hits]
