"""Store integration tokens encrypted with the workspace DEK."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import (
    decrypt_with_dek,
    encrypt_with_dek,
    unwrap_dek,
)
from app.core.errors import NotFoundError
from app.core.ulid import new_ulid
from app.models import Integration, WorkspaceKey


async def _dek_for_workspace(db: AsyncSession, workspace_id: str) -> bytes:
    wk = (await db.execute(
        select(WorkspaceKey).where(WorkspaceKey.workspace_id == workspace_id)
    )).scalar_one_or_none()
    if wk is None:
        raise NotFoundError("workspace_key", workspace_id)
    return unwrap_dek(wk.dek_ciphertext, master_key_b64=get_settings().master_key)


async def upsert_integration(
    db: AsyncSession,
    *,
    workspace_id: str,
    kind: str,
    raw_token: str,
    config: dict[str, Any],
) -> Integration:
    dek = await _dek_for_workspace(db, workspace_id)
    ciphertext = encrypt_with_dek(raw_token, dek=dek)

    existing = (await db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id, Integration.kind == kind
        )
    )).scalar_one_or_none()

    if existing is not None:
        existing.token_ciphertext = ciphertext
        existing.config = config
        await db.flush()
        return existing

    integration = Integration(
        id=new_ulid(),
        workspace_id=workspace_id,
        kind=kind,
        token_ciphertext=ciphertext,
        config=config,
    )
    db.add(integration)
    await db.flush()
    return integration


async def get_integration(
    db: AsyncSession, *, workspace_id: str, kind: str,
) -> Integration | None:
    return (await db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id, Integration.kind == kind
        )
    )).scalar_one_or_none()


async def get_decrypted_token(
    db: AsyncSession, *, workspace_id: str, kind: str,
) -> str:
    integ = await get_integration(db, workspace_id=workspace_id, kind=kind)
    if integ is None or not integ.token_ciphertext:
        raise NotFoundError("integration", kind)
    dek = await _dek_for_workspace(db, workspace_id)
    return decrypt_with_dek(integ.token_ciphertext, dek=dek)


async def delete_integration(
    db: AsyncSession, *, workspace_id: str, kind: str,
) -> None:
    integ = await get_integration(db, workspace_id=workspace_id, kind=kind)
    if integ is None:
        raise NotFoundError("integration", kind)
    await db.delete(integ)
    await db.flush()


async def list_integrations(
    db: AsyncSession, *, workspace_id: str,
) -> list[Integration]:
    rows = (await db.execute(
        select(Integration)
        .where(Integration.workspace_id == workspace_id)
        .order_by(Integration.connected_at.desc())
    )).scalars()
    return list(rows)


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    """Strip any secret-like keys from config before returning to client."""
    return {k: v for k, v in config.items() if k not in {"access_token", "refresh_token", "token"}}
