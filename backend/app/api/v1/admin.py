"""Admin dashboard — production overview + admin actions.

Mounts at /api/v1/admin/*. Three classes of routes:

  • Read overview  — KPIs aggregating users, subscriptions, ships,
    sessions, MRR, etc. Gated by require_admin (auth + email-allowlist
    + is_admin DB flag, all three). Cheap to refresh; the dashboard
    polls every 30s.
  • Read details   — paginated lists (users, recent stripe events,
    audit log).
  • Write actions  — gated by require_admin_2fa on top of the above.
    Every successful write call logs to admin_audit_log via
    log_admin_action().

Stripe coupon CRUD calls Stripe directly. The launch coupon was
created server-side once via ops/stripe-setup.py; this endpoint surface
makes ad-hoc coupon issuance a one-call operation from the dashboard.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import stripe
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import (
    AdminContext,
    log_admin_action,
    require_admin,
    require_admin_2fa,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import HangarError, NotFoundError, ValidationError
from app.models import (
    AdminAuditLog,
    Decision,
    Plan,
    Project,
    Ship,
    StripeEvent,
    Subscription,
    User,
    Workspace,
)
from app.models import (
    Session as SessionModel,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[AdminContext, Depends(require_admin)]
AdminWriteDep = Annotated[AdminContext, Depends(require_admin_2fa)]


# ---------------------------------------------------------------------------
# Overview KPIs
# ---------------------------------------------------------------------------

class KPIBlock(BaseModel):
    label: str
    value: int | float | str
    accent: str | None = None  # 'green' | 'amber' | 'red' | None
    delta: str | None = None   # eg "+3 today"


class OverviewOut(BaseModel):
    kpis: list[KPIBlock]
    subs_by_status: dict[str, int]
    mrr_eur: float
    arr_eur: float
    generated_at: str


@router.get("/overview", response_model=OverviewOut)
async def overview(_: AdminDep, db: DbDep) -> OverviewOut:
    """One-call aggregate snapshot. Designed to be cheap enough to poll
    every 30 seconds from the dashboard."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    # ── Users ────────────────────────────────────────────────────────────
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    new_today = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
    ).scalar_one()
    new_week = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= week_start)
        )
    ).scalar_one()

    # ── Subscriptions by status ─────────────────────────────────────────
    sub_rows = (
        await db.execute(
            select(Subscription.status, func.count(Subscription.id))
            .group_by(Subscription.status)
        )
    ).all()
    subs_by_status: dict[str, int] = {row[0]: int(row[1]) for row in sub_rows}
    paying = subs_by_status.get("active", 0) + subs_by_status.get("trialing", 0)

    # ── MRR / ARR ────────────────────────────────────────────────────────
    # Sum (active + trialing) subscriptions x their plan price. Trialing
    # users don't pay yet but they're committed; including them gives us
    # "expected MRR" which is the more useful metric.
    plan_rows = (
        await db.execute(select(Plan).where(Plan.slug.in_(["pro"])))
    ).scalars().all()
    plans_by_id = {p.id: p for p in plan_rows}
    revenue_rows = (
        await db.execute(
            select(Subscription.plan_id, func.count(Subscription.id))
            .where(Subscription.status.in_(["active", "trialing"]))
            .group_by(Subscription.plan_id)
        )
    ).all()
    mrr_cents = 0
    for plan_id, count in revenue_rows:
        plan = plans_by_id.get(plan_id)
        if plan is None:
            continue
        # Plan price is in cents; assume monthly cadence for the headline
        # MRR (annual subs would be amortised but our `pro` plan is
        # monthly-priced so this is correct for the current pricing model).
        mrr_cents += int(plan.monthly_price_eur_cents) * int(count)
    mrr_eur = round(mrr_cents / 100, 2)
    arr_eur = round(mrr_eur * 12, 2)

    # ── Project / Ship / Session activity ───────────────────────────────
    total_projects = (await db.execute(select(func.count(Project.id)))).scalar_one()
    ships_today = (
        await db.execute(
            select(func.count(Ship.id)).where(Ship.shipped_at >= today_start)
        )
    ).scalar_one()
    ships_week = (
        await db.execute(
            select(func.count(Ship.id)).where(Ship.shipped_at >= week_start)
        )
    ).scalar_one()
    sessions_today = (
        await db.execute(
            select(func.count(SessionModel.id))
            .where(SessionModel.started_at >= today_start)
        )
    ).scalar_one()
    sessions_month = (
        await db.execute(
            select(func.count(SessionModel.id))
            .where(SessionModel.started_at >= month_start)
        )
    ).scalar_one()

    # ── Compose KPI blocks ──────────────────────────────────────────────
    kpis: list[KPIBlock] = [
        KPIBlock(
            label="users",
            value=int(total_users),
            delta=f"+{int(new_today)} today" if new_today else None,
            accent="green" if new_today else None,
        ),
        KPIBlock(
            label="paying",
            value=int(paying),
            accent="green" if paying else "amber",
        ),
        KPIBlock(
            label="MRR",
            value=f"€{mrr_eur:.2f}",
            accent="green" if mrr_eur > 0 else None,
        ),
        KPIBlock(
            label="ARR",
            value=f"€{arr_eur:.2f}",
        ),
        KPIBlock(label="projects", value=int(total_projects)),
        KPIBlock(
            label="ships · 7d",
            value=int(ships_week),
            delta=f"{int(ships_today)} today" if ships_today else None,
        ),
        KPIBlock(
            label="sessions · 30d",
            value=int(sessions_month),
            delta=f"{int(sessions_today)} today" if sessions_today else None,
        ),
        KPIBlock(label="signups · 7d", value=int(new_week)),
    ]

    return OverviewOut(
        kpis=kpis,
        subs_by_status=subs_by_status,
        mrr_eur=mrr_eur,
        arr_eur=arr_eur,
        generated_at=now.isoformat(),
    )


# ---------------------------------------------------------------------------
# Users list + detail
# ---------------------------------------------------------------------------

class UserRow(BaseModel):
    id: str
    email: str
    name: str | None
    created_at: str | None
    email_verified_at: str | None
    is_admin: bool
    totp_enabled: bool
    workspace_count: int
    sub_status: str | None
    sub_trial_ends_at: str | None


class UsersListOut(BaseModel):
    items: list[UserRow]
    total: int


@router.get("/users", response_model=UsersListOut)
async def list_users(
    _: AdminDep,
    db: DbDep,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UsersListOut:
    """Search + paginate users. Joins workspaces (count) + subscriptions
    (status + trial_ends_at). Substring match on email."""
    base_stmt = select(User)
    count_stmt = select(func.count(User.id))
    if q:
        like = f"%{q.lower().strip()}%"
        base_stmt = base_stmt.where(func.lower(User.email).like(like))
        count_stmt = count_stmt.where(func.lower(User.email).like(like))

    total = int((await db.execute(count_stmt)).scalar_one())
    users = list(
        (
            await db.execute(
                base_stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)
            )
        ).scalars().all()
    )

    if not users:
        return UsersListOut(items=[], total=total)

    user_ids = [u.id for u in users]
    ws_count_rows = (
        await db.execute(
            select(Workspace.owner_id, func.count(Workspace.id))
            .where(Workspace.owner_id.in_(user_ids))
            .group_by(Workspace.owner_id)
        )
    ).all()
    # Explicit dict construction — feeding a Sequence[Row[...]] directly
    # to dict() trips mypy because Row's tuple shape is wider than what
    # dict() narrowly expects.
    ws_counts: dict[str, int] = {row[0]: int(row[1]) for row in ws_count_rows}
    sub_rows = (
        await db.execute(
            select(Subscription).where(Subscription.user_id.in_(user_ids))
        )
    ).scalars().all()
    subs_by_user = {s.user_id: s for s in sub_rows}

    items: list[UserRow] = []
    for u in users:
        sub = subs_by_user.get(u.id)
        trial_ends_at_iso: str | None = None
        if sub is not None and sub.trial_ends_at is not None:
            trial_ends_at_iso = sub.trial_ends_at.isoformat()
        items.append(
            UserRow(
                id=u.id,
                email=u.email,
                name=u.name,
                created_at=u.created_at.isoformat() if u.created_at else None,
                email_verified_at=u.email_verified_at.isoformat() if u.email_verified_at else None,
                is_admin=bool(u.is_admin),
                totp_enabled=bool(u.totp_secret_enc and u.totp_enabled_at),
                workspace_count=int(ws_counts.get(u.id, 0)),
                sub_status=sub.status if sub is not None else None,
                sub_trial_ends_at=trial_ends_at_iso,
            )
        )
    return UsersListOut(items=items, total=total)


class UserDetailOut(BaseModel):
    user: UserRow
    workspaces: list[dict[str, Any]]
    project_count: int
    session_count: int
    ship_count: int
    decision_count: int
    last_session_at: str | None


@router.get("/users/{user_id}", response_model=UserDetailOut)
async def user_detail(user_id: str, _: AdminDep, db: DbDep) -> UserDetailOut:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("user", user_id)

    ws_rows = (
        await db.execute(
            select(Workspace).where(Workspace.owner_id == user.id)
        )
    ).scalars().all()
    workspace_ids = [w.id for w in ws_rows]
    workspaces = [
        {"id": w.id, "slug": w.slug, "name": w.name, "plan": w.plan} for w in ws_rows
    ]

    project_count = 0
    session_count = 0
    ship_count = 0
    decision_count = 0
    last_session_at: str | None = None
    if workspace_ids:
        project_count = int(
            (
                await db.execute(
                    select(func.count(Project.id)).where(
                        Project.workspace_id.in_(workspace_ids)
                    )
                )
            ).scalar_one()
        )
        session_count = int(
            (
                await db.execute(
                    select(func.count(SessionModel.id)).join(
                        Project, Project.id == SessionModel.project_id
                    ).where(Project.workspace_id.in_(workspace_ids))
                )
            ).scalar_one()
        )
        ship_count = int(
            (
                await db.execute(
                    select(func.count(Ship.id)).join(
                        Project, Project.id == Ship.project_id
                    ).where(Project.workspace_id.in_(workspace_ids))
                )
            ).scalar_one()
        )
        decision_count = int(
            (
                await db.execute(
                    select(func.count(Decision.id)).join(
                        Project, Project.id == Decision.project_id
                    ).where(Project.workspace_id.in_(workspace_ids))
                )
            ).scalar_one()
        )
        latest = (
            await db.execute(
                select(SessionModel.started_at).join(
                    Project, Project.id == SessionModel.project_id
                ).where(Project.workspace_id.in_(workspace_ids))
                .order_by(desc(SessionModel.started_at)).limit(1)
            )
        ).scalar_one_or_none()
        if latest:
            last_session_at = latest.isoformat()

    sub = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalar_one_or_none()

    user_row = UserRow(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at.isoformat() if user.created_at else None,
        email_verified_at=user.email_verified_at.isoformat() if user.email_verified_at else None,
        is_admin=bool(user.is_admin),
        totp_enabled=bool(user.totp_secret_enc and user.totp_enabled_at),
        workspace_count=len(ws_rows),
        sub_status=sub.status if sub else None,
        sub_trial_ends_at=sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
    )
    return UserDetailOut(
        user=user_row,
        workspaces=workspaces,
        project_count=project_count,
        session_count=session_count,
        ship_count=ship_count,
        decision_count=decision_count,
        last_session_at=last_session_at,
    )


# ---------------------------------------------------------------------------
# Recent activity feed
# ---------------------------------------------------------------------------

class ActivityRow(BaseModel):
    kind: str  # "signup" | "ship" | "decision" | "stripe_event"
    at: str
    title: str
    detail: str | None = None
    target_id: str | None = None


class ActivityOut(BaseModel):
    items: list[ActivityRow]


@router.get("/recent-activity", response_model=ActivityOut)
async def recent_activity(_: AdminDep, db: DbDep, limit: int = Query(default=30, ge=1, le=200)) -> ActivityOut:
    """Last N events across signups, ships, decisions, stripe events.
    Cheaply rendered; designed for the right-rail of the admin page."""
    since = datetime.now(UTC) - timedelta(days=14)

    signups = (
        await db.execute(
            select(User)
            .where(User.created_at >= since)
            .order_by(desc(User.created_at)).limit(limit)
        )
    ).scalars().all()
    ships = (
        await db.execute(
            select(Ship, Project)
            .join(Project, Project.id == Ship.project_id)
            .where(Ship.shipped_at >= since)
            .order_by(desc(Ship.shipped_at)).limit(limit)
        )
    ).all()
    decisions = (
        await db.execute(
            select(Decision, Project)
            .join(Project, Project.id == Decision.project_id)
            .where(Decision.created_at >= since)
            .order_by(desc(Decision.created_at)).limit(limit)
        )
    ).all()
    stripe_events = (
        await db.execute(
            select(StripeEvent)
            .order_by(desc(StripeEvent.processed_at)).limit(limit)
        )
    ).scalars().all()

    items: list[ActivityRow] = []
    for u in signups:
        if u.created_at:
            items.append(ActivityRow(
                kind="signup",
                at=u.created_at.isoformat(),
                title=f"New signup · {u.email}",
                target_id=u.id,
            ))
    for ship, project in ships:
        items.append(ActivityRow(
            kind="ship",
            at=ship.shipped_at.isoformat() if ship.shipped_at else "",
            title=f"Ship · {project.slug} {ship.version or ''}".strip(),
            detail=ship.summary,
            target_id=ship.id,
        ))
    for d, project in decisions:
        items.append(ActivityRow(
            kind="decision",
            at=d.created_at.isoformat() if d.created_at else "",
            title=f"Decision · {project.slug}",
            detail=d.title,
            target_id=d.id,
        ))
    for ev in stripe_events:
        items.append(ActivityRow(
            kind="stripe_event",
            at=ev.processed_at.isoformat() if ev.processed_at else "",
            title=f"Stripe · {ev.type}",
            target_id=ev.id,
        ))

    items.sort(key=lambda x: x.at, reverse=True)
    return ActivityOut(items=items[:limit])


# ---------------------------------------------------------------------------
# Coupons (Stripe)
# ---------------------------------------------------------------------------

class CouponRow(BaseModel):
    id: str
    name: str | None
    percent_off: float | None
    amount_off: int | None
    currency: str | None
    duration: str
    duration_in_months: int | None
    max_redemptions: int | None
    times_redeemed: int
    valid: bool


class CouponsOut(BaseModel):
    items: list[CouponRow]


def _stripe_ready() -> None:
    key = get_settings().stripe_secret_key
    if not key:
        raise HangarError(
            title="Stripe not configured",
            status=503, type_="/errors/stripe-disabled",
            detail="HANGAR_STRIPE_SECRET_KEY is empty",
        )
    stripe.api_key = key


@router.get("/coupons", response_model=CouponsOut)
async def list_coupons(_: AdminDep) -> CouponsOut:
    _stripe_ready()
    try:
        result = stripe.Coupon.list(limit=100)
    except stripe.StripeError as exc:
        logger.warning("admin.list_coupons: stripe error: %s", exc)
        raise HangarError(
            title="Stripe error", status=502,
            type_="/errors/stripe", detail=str(exc),
        ) from exc
    items: list[CouponRow] = []
    for c in result.auto_paging_iter():
        items.append(
            CouponRow(
                id=c.id,
                name=getattr(c, "name", None),
                percent_off=float(getattr(c, "percent_off", 0) or 0) or None,
                amount_off=int(getattr(c, "amount_off", 0) or 0) or None,
                currency=getattr(c, "currency", None),
                duration=str(getattr(c, "duration", "once")),
                duration_in_months=getattr(c, "duration_in_months", None),
                max_redemptions=getattr(c, "max_redemptions", None),
                times_redeemed=int(getattr(c, "times_redeemed", 0)),
                valid=bool(getattr(c, "valid", False)),
            )
        )
    return CouponsOut(items=items)


class CouponCreateIn(BaseModel):
    code: str = Field(..., min_length=3, max_length=40)
    name: str | None = Field(default=None, max_length=40)
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off_cents: int | None = Field(default=None, ge=50, le=100000)
    currency: str = Field(default="eur", min_length=3, max_length=3)
    duration: str = Field(default="once", pattern="^(once|repeating|forever)$")
    duration_in_months: int | None = Field(default=None, ge=1, le=24)
    max_redemptions: int | None = Field(default=None, ge=1, le=10000)


@router.post("/coupons", response_model=CouponRow)
async def create_coupon(
    body: CouponCreateIn,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> CouponRow:
    """Create a new Stripe coupon. Either percent_off OR amount_off_cents
    must be set (Stripe rejects both/neither). The `code` becomes the
    coupon ID — case-sensitive, must be unique across your Stripe account."""
    _stripe_ready()
    if (body.percent_off is None) == (body.amount_off_cents is None):
        raise ValidationError(
            detail="set exactly one of percent_off / amount_off_cents",
        )
    if body.duration == "repeating" and not body.duration_in_months:
        raise ValidationError(detail="duration_in_months required for repeating")

    params: dict[str, Any] = {
        "id": body.code.strip(),
        "duration": body.duration,
    }
    if body.name:
        params["name"] = body.name.strip()
    if body.percent_off is not None:
        params["percent_off"] = body.percent_off
    if body.amount_off_cents is not None:
        params["amount_off"] = body.amount_off_cents
        params["currency"] = body.currency.lower()
    if body.duration_in_months:
        params["duration_in_months"] = body.duration_in_months
    if body.max_redemptions:
        params["max_redemptions"] = body.max_redemptions

    try:
        c = stripe.Coupon.create(**params)
    except stripe.StripeError as exc:
        logger.warning("admin.create_coupon: stripe error: %s", exc)
        raise HangarError(
            title="Stripe error", status=502,
            type_="/errors/stripe", detail=str(exc),
        ) from exc

    await log_admin_action(
        db, actor=admin.user, action="coupon.create",
        target_type="coupon", target_id=c.id,
        payload={k: v for k, v in params.items() if k != "id"},
        request=request,
    )
    await db.commit()

    return CouponRow(
        id=c.id,
        name=getattr(c, "name", None),
        percent_off=float(getattr(c, "percent_off", 0) or 0) or None,
        amount_off=int(getattr(c, "amount_off", 0) or 0) or None,
        currency=getattr(c, "currency", None),
        duration=str(getattr(c, "duration", "once")),
        duration_in_months=getattr(c, "duration_in_months", None),
        max_redemptions=getattr(c, "max_redemptions", None),
        times_redeemed=int(getattr(c, "times_redeemed", 0)),
        valid=bool(getattr(c, "valid", False)),
    )


@router.delete("/coupons/{coupon_id}", status_code=204)
async def delete_coupon(
    coupon_id: str,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> None:
    _stripe_ready()
    try:
        stripe.Coupon.delete(coupon_id)
    except stripe.StripeError as exc:
        raise HangarError(
            title="Stripe error", status=502,
            type_="/errors/stripe", detail=str(exc),
        ) from exc
    await log_admin_action(
        db, actor=admin.user, action="coupon.delete",
        target_type="coupon", target_id=coupon_id,
        request=request,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Subscription actions (extend trial / comp month)
# ---------------------------------------------------------------------------

class TrialExtendIn(BaseModel):
    days: int = Field(..., ge=1, le=180)


@router.post("/users/{user_id}/extend-trial")
async def extend_trial(
    user_id: str,
    body: TrialExtendIn,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> dict[str, Any]:
    """Push the user's `trial_ends_at` further into the future. Works on
    DB-level Subscription rows; does NOT call Stripe (Stripe-side trial
    extensions require a different flow we'll wire when needed)."""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("user", user_id)
    sub = (
        await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalar_one_or_none()
    if sub is None:
        raise NotFoundError("subscription", user_id)

    base = sub.trial_ends_at if sub.trial_ends_at and sub.trial_ends_at > datetime.now(UTC) else datetime.now(UTC)
    sub.trial_ends_at = base + timedelta(days=body.days)
    if sub.status not in ("trialing", "active"):
        sub.status = "trialing"
    await db.flush()

    await log_admin_action(
        db, actor=admin.user, action="trial.extend",
        target_type="user", target_id=user.id,
        payload={"days": body.days, "new_trial_ends_at": sub.trial_ends_at.isoformat()},
        request=request,
    )
    await db.commit()
    return {
        "user_id": user.id,
        "trial_ends_at": sub.trial_ends_at.isoformat(),
        "status": sub.status,
    }


# ---------------------------------------------------------------------------
# Audit log read
# ---------------------------------------------------------------------------

class AuditRow(BaseModel):
    id: str
    actor_user_id: str
    actor_email: str | None
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict[str, Any]
    ip: str | None
    at: str


class AuditOut(BaseModel):
    items: list[AuditRow]


@router.get("/audit-log", response_model=AuditOut)
async def audit_log(
    _: AdminDep,
    db: DbDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditOut:
    rows = (
        await db.execute(
            select(AdminAuditLog).order_by(desc(AdminAuditLog.at)).limit(limit)
        )
    ).scalars().all()
    actor_ids = list({r.actor_user_id for r in rows})
    actor_emails: dict[str, str] = {}
    if actor_ids:
        users = (
            await db.execute(select(User).where(User.id.in_(actor_ids)))
        ).scalars().all()
        actor_emails = {u.id: u.email for u in users}
    return AuditOut(
        items=[
            AuditRow(
                id=r.id,
                actor_user_id=r.actor_user_id,
                actor_email=actor_emails.get(r.actor_user_id),
                action=r.action,
                target_type=r.target_type,
                target_id=r.target_id,
                payload=r.payload or {},
                ip=r.ip,
                at=r.at.isoformat() if r.at else "",
            )
            for r in rows
        ]
    )
