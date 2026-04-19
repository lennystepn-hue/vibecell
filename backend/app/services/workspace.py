"""Workspace lifecycle helpers beyond first-login bootstrap."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import generate_dek, wrap_dek
from app.core.errors import ConflictError, ValidationError
from app.core.ulid import new_ulid
from app.models import User, Workspace, WorkspaceKey, WorkspaceMember

_RESERVED_SLUGS: frozenset[str] = frozenset(
    {"api", "admin", "public", "app", "www", "import", "settings", "billing", "auth"}
)


async def create_workspace(
    db: AsyncSession, *, owner: User, slug: str, name: str,
) -> Workspace:
    if slug in _RESERVED_SLUGS:
        raise ValidationError(detail=f"slug {slug!r} is reserved")

    existing = (await db.execute(select(Workspace.id).where(Workspace.slug == slug))).first()
    if existing is not None:
        raise ConflictError(detail=f"workspace slug {slug!r} already exists")

    ws = Workspace(id=new_ulid(), slug=slug, name=name, owner_id=owner.id)
    db.add(ws)
    await db.flush()

    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role="owner"))

    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=get_settings().master_key)
    db.add(WorkspaceKey(workspace_id=ws.id, dek_ciphertext=wrapped))

    await db.flush()
    return ws
