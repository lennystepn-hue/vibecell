"""Per-project secret refs — list/add/remove/resolve.

Inline-encrypted values round-trip through the workspace DEK. External
references (op://, bw://, ssh-agent://, env_path, keychain) store only the
locator; clients resolve them locally via the CLI resolver.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.schemas.secret import SecretIn, SecretOut, SecretValueOut
from app.services import secret as secret_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/secrets", tags=["secrets"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("", response_model=list[SecretOut])
async def list_(ctx: CtxDep, db: DbDep) -> list[SecretOut]:
    rows = await secret_svc.list_secrets(db, ctx.project)
    return [SecretOut.model_validate(secret_svc.to_out(r)) for r in rows]


@router.post("", response_model=SecretOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: SecretIn, ctx: CtxDep, auth: AuthDep, db: DbDep,
) -> SecretOut:
    row = await secret_svc.add_secret(
        db,
        ctx.project,
        label=body.label,
        kind=body.kind,
        reference=body.reference,
        workspace_id=auth.active_workspace_id,
    )
    await db.commit()
    return SecretOut.model_validate(secret_svc.to_out(row))


@router.delete("/{label}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(
    label: Annotated[str, Path(min_length=1, max_length=200)],
    ctx: CtxDep,
    db: DbDep,
) -> None:
    await secret_svc.remove_secret(db, ctx.project, label)
    await db.commit()


@router.get("/{label}/resolve", response_model=SecretValueOut)
async def resolve(
    label: Annotated[str, Path(min_length=1, max_length=200)],
    ctx: CtxDep,
    auth: AuthDep,
    db: DbDep,
) -> SecretValueOut:
    value = await secret_svc.get_decrypted_value(
        db, ctx.project, label, workspace_id=auth.active_workspace_id,
    )
    return SecretValueOut(value=value)
