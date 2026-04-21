"""Per-project labeled secret references (HANGAR.md §4.2).

Supported kinds:
    inline_encrypted  — value stored as workspace-DEK ciphertext
    op                — 1Password path (op://Vault/Item/field)
    bw                — Bitwarden path (bw://<item>[/<field>])
    ssh_agent         — ssh-agent://SHA256:... reference
    env_path          — resolver placeholder (reads $PATH var at exec)
    keychain          — OS-keychain reference placeholder

Only `inline_encrypted` ciphertext is sensitive at rest — the other `reference`
values are just locators and safe to persist in clear.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import decrypt_with_dek, encrypt_with_dek, unwrap_dek
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import Project, ProjectSecretRef, WorkspaceKey

INLINE_KIND = "inline_encrypted"
MASKED_REFERENCE = "******"


async def _dek_for_workspace(db: AsyncSession, workspace_id: str) -> bytes:
    wk = (await db.execute(
        select(WorkspaceKey).where(WorkspaceKey.workspace_id == workspace_id)
    )).scalar_one_or_none()
    if wk is None:
        raise NotFoundError("workspace_key", workspace_id)
    return unwrap_dek(wk.dek_ciphertext, master_key_b64=get_settings().master_key)


async def list_secrets(
    db: AsyncSession, project: Project,
) -> list[ProjectSecretRef]:
    rows = (await db.execute(
        select(ProjectSecretRef)
        .where(ProjectSecretRef.project_id == project.id)
        .order_by(ProjectSecretRef.created_at.asc())
    )).scalars()
    return list(rows)


async def get_secret(
    db: AsyncSession, project: Project, label: str,
) -> ProjectSecretRef | None:
    return (await db.execute(
        select(ProjectSecretRef).where(
            ProjectSecretRef.project_id == project.id,
            ProjectSecretRef.label == label,
        )
    )).scalar_one_or_none()


async def add_secret(
    db: AsyncSession,
    project: Project,
    *,
    label: str,
    kind: str,
    reference: str,
    workspace_id: str,
) -> ProjectSecretRef:
    existing = await get_secret(db, project, label)
    if existing is not None:
        raise ConflictError(
            detail=f"secret with label {label!r} already exists on project",
        )

    stored_reference = reference
    if kind == INLINE_KIND:
        dek = await _dek_for_workspace(db, workspace_id)
        stored_reference = encrypt_with_dek(reference, dek=dek)

    row = ProjectSecretRef(
        id=new_ulid(),
        project_id=project.id,
        label=label,
        kind=kind,
        reference=stored_reference,
    )
    db.add(row)
    await db.flush()
    return row


async def remove_secret(
    db: AsyncSession, project: Project, label: str,
) -> None:
    row = await get_secret(db, project, label)
    if row is None:
        raise NotFoundError("secret", label)
    await db.delete(row)
    await db.flush()


async def get_decrypted_value(
    db: AsyncSession,
    project: Project,
    label: str,
    *,
    workspace_id: str,
) -> str:
    row = await get_secret(db, project, label)
    if row is None:
        raise NotFoundError("secret", label)
    if row.kind != INLINE_KIND:
        raise ValidationError(
            detail=(
                f"secret {label!r} is kind={row.kind!r}; only inline_encrypted "
                "secrets can be resolved via this endpoint"
            ),
        )
    dek = await _dek_for_workspace(db, workspace_id)
    value = decrypt_with_dek(row.reference, dek=dek)
    # Record usage so the UI can show "@LABEL used Xm ago".
    row.last_used_at = datetime.now(UTC)
    await db.flush()
    return value


async def touch_last_used(
    db: AsyncSession, project: Project, label: str,
) -> None:
    """Mark a secret as just-used even if the caller didn't decrypt
    (e.g. when returning an op:// path to Claude)."""
    row = await get_secret(db, project, label)
    if row is not None:
        row.last_used_at = datetime.now(UTC)
        await db.flush()


def to_out(row: ProjectSecretRef) -> dict[str, str | None]:
    """Shape a row for SecretOut, masking inline ciphertext."""
    return {
        "id": row.id,
        "label": row.label,
        "kind": row.kind,
        "reference": MASKED_REFERENCE if row.kind == INLINE_KIND else row.reference,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }
