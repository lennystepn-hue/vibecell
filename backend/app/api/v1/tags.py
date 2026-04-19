"""Workspace tags."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.schemas.tag import TagCreate, TagOut
from app.services import catalog as svc

router = APIRouter(prefix="/api/v1/tags", tags=["catalog"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("", response_model=list[TagOut])
async def list_(auth: AuthDep, db: DbDep) -> list[TagOut]:
    tags = await svc.list_tags(db, workspace_id=auth.active_workspace_id)
    return [TagOut.model_validate(t) for t in tags]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: TagCreate,
    auth: AuthDep,
    db: DbDep,
) -> TagOut:
    tag = await svc.create_tag(
        db, workspace_id=auth.active_workspace_id, name=body.name, color=body.color,
    )
    await db.commit()
    return TagOut.model_validate(tag)
