"""Global stack-items catalog."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.schemas.stack_item import StackItemCreate, StackItemOut
from app.services import catalog as svc

router = APIRouter(prefix="/api/v1/stack-items", tags=["catalog"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("", response_model=list[StackItemOut])
async def list_(
    _auth: AuthDep,
    db: DbDep,
    q: str | None = None,
    kind: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[StackItemOut]:
    items = await svc.search_stack_items(db, q=q, kind=kind, limit=limit)
    return [StackItemOut.model_validate(i) for i in items]


@router.post("", response_model=StackItemOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: StackItemCreate,
    _auth: AuthDep,
    db: DbDep,
) -> StackItemOut:
    item = await svc.create_stack_item(
        db, slug=body.slug, name=body.name, kind=body.kind, icon_url=body.icon_url,
    )
    await db.commit()
    return StackItemOut.model_validate(item)
