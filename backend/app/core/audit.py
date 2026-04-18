"""SQLAlchemy audit listener + request-scoped context vars.

`install_audit_listener()` wires a `before_flush` event on `Session`
that inspects `session.new`, `session.dirty`, and `session.deleted` and
emits `AuditLog` rows for each non-`AuditLog` instance.

Actor and workspace_id come from contextvars set by middleware (Phase 3)
or tests. If they aren't set when a write happens, the listener falls
back to `actor='system'` and uses the record's `workspace_id` attribute
when the entity has one — otherwise the write is allowed but not logged
(entities without workspace_id cannot satisfy the NOT NULL audit_log
column, so we skip logging for them).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.ulid import new_ulid
from app.models import AuditLog

current_actor: ContextVar[str] = ContextVar("current_actor", default="system")
current_workspace_id: ContextVar[str | None] = ContextVar("current_workspace_id", default=None)

_installed = False


def _extract_diff(obj: Any, op: str) -> dict[str, Any]:
    """Return {column: [before, after]} for update, {column: [None, after]} for create,
    {column: [before, None]} for delete. Skips columns whose value didn't change."""
    state = inspect(obj)
    mapper = state.mapper

    diff: dict[str, Any] = {}
    for col in mapper.column_attrs:
        name = col.key
        hist = state.attrs[name].history
        if op == "create":
            if hist.added:
                value = hist.added[0]
                diff[name] = [None, _jsonify(value)]
        elif op == "update":
            if hist.has_changes():
                before = hist.deleted[0] if hist.deleted else None
                after = hist.added[0] if hist.added else None
                diff[name] = [_jsonify(before), _jsonify(after)]
        elif op == "delete":
            # On delete, history has the original loaded value in `unchanged` or `deleted`.
            current_val = getattr(obj, name, None)
            diff[name] = [_jsonify(current_val), None]
    return diff


def _jsonify(value: Any) -> Any:
    """Convert non-JSON-safe values (datetime, bytes) to strings."""
    from datetime import date, datetime
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def install_audit_listener() -> None:
    """Idempotently attach the audit listener to all Session instances.

    SQLAlchemy async routes `AsyncSession` events through the underlying sync
    `Session`, so attaching to `Session.before_flush` catches async flushes too.
    """
    global _installed
    if _installed:
        return

    @event.listens_for(Session, "before_flush")
    def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
        actor = current_actor.get()
        workspace_id = current_workspace_id.get()

        audit_rows: list[AuditLog] = []

        def _collect(obj: Any, op: str) -> None:
            if isinstance(obj, AuditLog):
                return
            diff = _extract_diff(obj, op)
            ws_id = workspace_id or getattr(obj, "workspace_id", None)
            if not isinstance(ws_id, str):
                return  # no workspace context -> skip audit (e.g. users, magic_link_tokens)
            entity = obj.__tablename__
            entity_id = getattr(obj, "id", None)
            if not isinstance(entity_id, str):
                return  # composite PKs (workspace_members, project_stack, project_tags) — skip for v1
            audit_rows.append(AuditLog(
                id=new_ulid(),
                workspace_id=ws_id,
                actor=actor,
                op=op,
                entity=entity,
                entity_id=entity_id,
                diff=diff,
            ))

        for obj in list(session.new):
            _collect(obj, "create")
        for obj in list(session.dirty):
            if session.is_modified(obj, include_collections=False):
                _collect(obj, "update")
        for obj in list(session.deleted):
            _collect(obj, "delete")

        for row in audit_rows:
            session.add(row)

    _installed = True
