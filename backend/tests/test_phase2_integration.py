from __future__ import annotations

import base64
import secrets
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import current_actor, current_workspace_id, install_audit_listener
from app.core.crypto import decrypt_with_dek, encrypt_with_dek, generate_dek, unwrap_dek, wrap_dek
from app.core.rate_limit import check_and_consume
from app.core.ulid import new_ulid
from app.models import AuditLog, Integration, User, Workspace, WorkspaceKey

pytestmark = pytest.mark.integration


async def test_workspace_creation_full_stack(session: AsyncSession) -> None:
    """User signs up -> workspace created -> DEK generated + wrapped -> GitHub token encrypted.
    Rate-limit allows N ops; audit log captures every write."""
    install_audit_listener()

    master_key_b64 = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    # Bootstrap user + workspace
    user = User(email=f"int-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()

    workspace = Workspace(slug=f"ws-{new_ulid()[:10]}", name="Integration", owner_id=user.id)
    session.add(workspace)
    await session.flush()

    token_actor = current_actor.set(f"ui:{user.id}")
    token_ws = current_workspace_id.set(workspace.id)
    try:
        # Generate + wrap DEK
        dek = generate_dek()
        wrapped = wrap_dek(dek, master_key_b64=master_key_b64)
        session.add(WorkspaceKey(workspace_id=workspace.id, dek_ciphertext=wrapped))

        # Encrypt a fake GitHub token with the DEK
        gh_token = "ghp_" + secrets.token_hex(20)
        ciphertext = encrypt_with_dek(gh_token, dek=dek)
        session.add(Integration(
            workspace_id=workspace.id, kind="github",
            config={"login": "lenny"}, token_ciphertext=ciphertext,
        ))
        await session.flush()

        # Round-trip: read the integration back, unwrap DEK, decrypt token
        result = await session.execute(
            select(Integration).where(
                Integration.workspace_id == workspace.id, Integration.kind == "github"
            )
        )
        stored = result.scalar_one()
        assert stored.token_ciphertext

        wk = (await session.execute(
            select(WorkspaceKey).where(WorkspaceKey.workspace_id == workspace.id)
        )).scalar_one()
        dek_out = unwrap_dek(wk.dek_ciphertext, master_key_b64=master_key_b64)
        recovered = decrypt_with_dek(stored.token_ciphertext, dek=dek_out)
        assert recovered == gh_token

        # Rate-limit: 2 attempts should pass, 3rd should fail
        rl_key = f"phase2-rl-{uuid.uuid4()}"
        r1, _ = await check_and_consume(rl_key, capacity=2, refill_rate=0.01)
        r2, _ = await check_and_consume(rl_key, capacity=2, refill_rate=0.01)
        r3, retry = await check_and_consume(rl_key, capacity=2, refill_rate=0.01)
        assert r1 is True
        assert r2 is True
        assert r3 is False
        assert retry >= 1
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    # Audit captured the workspace-scoped writes (not user, not workspace itself —
    # those were created without an active workspace context).
    audit_rows = (await session.execute(select(AuditLog))).scalars().all()
    entities = {row.entity for row in audit_rows}
    assert "integrations" in entities
    assert "workspace_keys" in entities
