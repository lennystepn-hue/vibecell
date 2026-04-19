"""SQLAlchemy audit listener + request-scoped context vars.

`install_audit_listener()` wires a `before_flush` event on SQLAlchemy's
sync `Session` (which catches async flushes too — `AsyncSession` routes
events through the underlying sync `Session`). It inspects `session.new`,
`session.dirty`, and `session.deleted` and emits `AuditLog` rows for
each non-`AuditLog` instance that has a resolvable workspace_id and a
known primary key.

Actor and workspace_id come from contextvars set by middleware (Phase 3)
or tests. If actor is not set, defaults to "system". If workspace_id is
not set and the entity has `workspace_id`, that value is used; otherwise
the row is skipped (entities without workspace scope, like `users` at
signup, are not audited).

Diff shape:
  create: {col: [None, after]}
  update: {col: [before, after]} — only for columns that actually changed
  delete: {col: [before, None]} — uses the in-memory attribute value

Auto-managed timestamp columns (`created_at`, `updated_at`) are filtered
from update diffs so every edit doesn't log pointless timestamp churn.
Composite-primary-key rows serialise their PK as "v1:v2" joined with ":".
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import date, datetime
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.ulid import new_ulid
from app.models import AuditLog

current_actor: ContextVar[str] = ContextVar("current_actor", default="system")
current_workspace_id: ContextVar[str | None] = ContextVar("current_workspace_id", default=None)

_installed = False

# Entity tablenames that are never audited (authn-sensitive or out-of-scope)
_AUDIT_SKIP_ENTITIES: frozenset[str] = frozenset(
    {
        "audit_log",           # no recursion (also guarded by isinstance below)
        "magic_link_tokens",   # authn tokens — out of scope by design
        "users",               # user identity changes audited via Spec 4 passkey flow
    }
)

# Column names filtered from update diffs (auto-managed by TimestampMixin /
# server_default). Still logged on create (useful for reconstruction).
_AUDIT_SKIP_COLUMNS_ON_UPDATE: frozenset[str] = frozenset({"created_at", "updated_at"})


def _jsonify(value: Any) -> Any:
    """Convert non-JSON-safe values (datetime, bytes) to strings."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def _resolve_entity_id(obj: Any, op: str) -> str | None:
    """Serialise an ORM instance's primary-key value to a single string.

    - Single-column PK: returns its string value (or None if unset).
    - Composite PK: joins column values with ':' (e.g., "<workspace_id>:<user_id>").

    On `create`, nudge any callable default (e.g. ulid_pk's `new_ulid`) so the
    PK is populated *before* flush — SQLAlchemy normally applies column
    defaults mid-flush (after `before_flush` has fired), which would leave
    the audit row referencing `None`.
    """
    state = inspect(obj)
    pk_cols = state.mapper.primary_key
    values: list[str] = []
    for col in pk_cols:
        v = getattr(obj, col.key, None)
        if v is None:
            if op == "create" and col.default is not None:
                default = col.default
                if getattr(default, "is_callable", False):
                    v = default.arg(None)  # ColumnDefault.arg is the callable
                elif getattr(default, "is_scalar", False):
                    v = default.arg
                else:
                    return None
                if v is None:
                    return None
                setattr(obj, col.key, v)
            else:
                return None
        values.append(str(v))
    return ":".join(values)


def _extract_diff(obj: Any, op: str) -> dict[str, Any]:
    """Return a JSONB-ready diff dict for the given operation."""
    state = inspect(obj)
    mapper = state.mapper

    diff: dict[str, Any] = {}
    for col in mapper.column_attrs:
        name = col.key
        hist = state.attrs[name].history
        if op == "create":
            if hist.added:
                diff[name] = [None, _jsonify(hist.added[0])]
        elif op == "update":
            if name in _AUDIT_SKIP_COLUMNS_ON_UPDATE:
                continue
            if hist.has_changes():
                before = hist.deleted[0] if hist.deleted else None
                after = hist.added[0] if hist.added else None
                diff[name] = [_jsonify(before), _jsonify(after)]
        elif op == "delete":
            current_val = getattr(obj, name, None)
            diff[name] = [_jsonify(current_val), None]
    return diff


def install_audit_listener() -> None:
    """Idempotently attach the audit listener to all Session instances."""
    global _installed
    if _installed:
        return

    @event.listens_for(Session, "before_flush")
    def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
        actor = current_actor.get()
        ctx_workspace_id = current_workspace_id.get()

        audit_rows: list[AuditLog] = []

        def _collect(obj: Any, op: str) -> None:
            if isinstance(obj, AuditLog):
                return
            entity = obj.__tablename__
            if entity in _AUDIT_SKIP_ENTITIES:
                return

            ws_id = ctx_workspace_id or getattr(obj, "workspace_id", None)
            if not isinstance(ws_id, str):
                return

            entity_id = _resolve_entity_id(obj, op)
            if entity_id is None:
                return

            diff = _extract_diff(obj, op)
            # Skip no-op updates (only filtered columns changed → empty diff).
            if op == "update" and not diff:
                return

            audit_rows.append(
                AuditLog(
                    id=new_ulid(),
                    workspace_id=ws_id,
                    actor=actor,
                    op=op,
                    entity=entity,
                    entity_id=entity_id,
                    diff=diff,
                )
            )

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
