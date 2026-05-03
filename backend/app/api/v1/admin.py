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
from app.jobs.trial_lifecycle import sync_subscription_to_stripe
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
from app.services.account_purge import purge as purge_user_data

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
    # Effective status — same as sub_status EXCEPT when DB says
    # "trialing" but trial_ends_at is in the past. The hourly cron
    # eventually flips these to past_due, but the dashboard shouldn't
    # wait an hour to display the truth.
    effective_status: str | None
    sub_trial_ends_at: str | None
    sub_trial_email_stage: str | None
    has_stripe_subscription: bool


def _effective_status(sub: Subscription | None, now: datetime) -> str | None:
    """Render-time correction for "trialing" rows whose trial_ends_at
    is in the past. The cron flips these on the next hourly tick; the
    dashboard pretends it already happened so the UI never lies."""
    if sub is None:
        return None
    if (
        sub.status == "trialing"
        and sub.trial_ends_at is not None
        and sub.trial_ends_at <= now
    ):
        return "expired_trial"
    return sub.status


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

    now = datetime.now(UTC)
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
                effective_status=_effective_status(sub, now),
                sub_trial_ends_at=trial_ends_at_iso,
                sub_trial_email_stage=sub.trial_email_stage if sub is not None else None,
                has_stripe_subscription=bool(sub and sub.stripe_subscription_id),
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

    now = datetime.now(UTC)
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
        effective_status=_effective_status(sub, now),
        sub_trial_ends_at=sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
        sub_trial_email_stage=sub.trial_email_stage if sub else None,
        has_stripe_subscription=bool(sub and sub.stripe_subscription_id),
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


async def _resolve_user_sub(
    db: AsyncSession, user_id: str,
) -> tuple[User, Subscription]:
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
    return user, sub


@router.post("/users/{user_id}/extend-trial")
async def extend_trial(
    user_id: str,
    body: TrialExtendIn,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> dict[str, Any]:
    """Push trial_ends_at further into the future + reset email-stage so
    the warning emails fire again. ALSO syncs to Stripe when the
    subscription has a stripe_subscription_id (so the customer's
    Stripe-side trial-end matches our DB)."""
    user, sub = await _resolve_user_sub(db, user_id)

    base = sub.trial_ends_at if sub.trial_ends_at and sub.trial_ends_at > datetime.now(UTC) else datetime.now(UTC)
    new_end = base + timedelta(days=body.days)
    sub.trial_ends_at = new_end
    sub.status = "trialing"
    # Reset the email state so warning + ended emails fire again on the
    # new trial cycle. Without this, an extended trial silently ends
    # without notification.
    sub.trial_email_stage = None
    await db.flush()

    stripe_status = await sync_subscription_to_stripe(
        sub, intent="extend_trial", value=new_end,
    )

    await log_admin_action(
        db, actor=admin.user, action="trial.extend",
        target_type="user", target_id=user.id,
        payload={
            "days": body.days,
            "new_trial_ends_at": new_end.isoformat(),
            "stripe_sync": stripe_status,
        },
        request=request,
    )
    await db.commit()
    return {
        "user_id": user.id,
        "trial_ends_at": new_end.isoformat(),
        "status": sub.status,
        "stripe_sync": stripe_status,
    }


# ---------------------------------------------------------------------------
# More power actions: cancel / comp / verify / toggle-admin / delete
# ---------------------------------------------------------------------------

class CancelSubIn(BaseModel):
    reason: str = Field(..., min_length=2, max_length=200)
    immediate: bool = Field(
        default=False,
        description="True = cancel right now. False = cancel at period end (Stripe default).",
    )


@router.post("/users/{user_id}/cancel-subscription")
async def cancel_subscription(
    user_id: str,
    body: CancelSubIn,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> dict[str, Any]:
    """Cancel the user's subscription. DB always updates; Stripe sync
    happens when stripe_subscription_id is set."""
    user, sub = await _resolve_user_sub(db, user_id)

    if body.immediate:
        sub.status = "canceled"
        sub.cancel_at_period_end = False
        sub.trial_ends_at = None
    else:
        sub.cancel_at_period_end = True
    await db.flush()

    stripe_status = await sync_subscription_to_stripe(sub, intent="cancel")
    await log_admin_action(
        db, actor=admin.user, action="subscription.cancel",
        target_type="user", target_id=user.id,
        payload={"reason": body.reason, "immediate": body.immediate, "stripe_sync": stripe_status},
        request=request,
    )
    await db.commit()
    return {"user_id": user.id, "status": sub.status, "stripe_sync": stripe_status}


class CompDaysIn(BaseModel):
    days: int = Field(..., ge=1, le=365)
    reason: str = Field(..., min_length=2, max_length=200)


@router.post("/users/{user_id}/comp-days")
async def comp_days(
    user_id: str,
    body: CompDaysIn,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> dict[str, Any]:
    """Comp the user N days of free service. Sets status to "active"
    (or "trialing" if already in trial) and pushes either trial_ends_at
    or current_period_end forward by N days. Always updates DB; syncs
    to Stripe via trial_end if a Stripe sub exists."""
    user, sub = await _resolve_user_sub(db, user_id)
    now = datetime.now(UTC)

    # Use trial_ends_at when in trial, otherwise current_period_end. If
    # neither is set or both are in the past, anchor on now.
    if sub.status == "trialing" and sub.trial_ends_at and sub.trial_ends_at > now:
        new_end = sub.trial_ends_at + timedelta(days=body.days)
        sub.trial_ends_at = new_end
    elif sub.current_period_end and sub.current_period_end > now:
        new_end = sub.current_period_end + timedelta(days=body.days)
        sub.current_period_end = new_end
    else:
        new_end = now + timedelta(days=body.days)
        sub.trial_ends_at = new_end
        sub.status = "trialing"
    sub.trial_email_stage = None  # let trial-lifecycle send emails again on the new period
    await db.flush()

    stripe_status = await sync_subscription_to_stripe(
        sub, intent="extend_trial", value=new_end,
    )
    await log_admin_action(
        db, actor=admin.user, action="subscription.comp",
        target_type="user", target_id=user.id,
        payload={"days": body.days, "reason": body.reason, "new_end": new_end.isoformat(), "stripe_sync": stripe_status},
        request=request,
    )
    await db.commit()
    return {
        "user_id": user.id, "status": sub.status,
        "new_end": new_end.isoformat(), "stripe_sync": stripe_status,
    }


@router.post("/users/{user_id}/mark-email-verified")
async def mark_email_verified(
    user_id: str,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> dict[str, Any]:
    """Force-stamp users.email_verified_at = now(). Useful for support
    cases where the magic-link bounced but you've otherwise verified
    the user identity."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("user", user_id)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        await db.flush()
    await log_admin_action(
        db, actor=admin.user, action="user.mark_email_verified",
        target_type="user", target_id=user.id,
        payload={"email": user.email},
        request=request,
    )
    await db.commit()
    return {"user_id": user.id, "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None}


class ToggleAdminIn(BaseModel):
    is_admin: bool


@router.post("/users/{user_id}/toggle-admin")
async def toggle_admin(
    user_id: str,
    body: ToggleAdminIn,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> dict[str, Any]:
    """Promote / demote a user as admin. The HANGAR_ADMIN_EMAILS env list
    is the OTHER required gate — flipping is_admin alone doesn't grant
    admin access until the env list is also updated. By design (defense-
    in-depth)."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("user", user_id)

    # Defensive: don't let an admin demote themselves to nothing — would
    # lock the dashboard out if no other admins remain.
    if not body.is_admin and user.id == admin.user.id:
        other_admins = int(
            (
                await db.execute(
                    select(func.count(User.id))
                    .where(User.is_admin.is_(True))
                    .where(User.id != user.id)
                )
            ).scalar_one()
        )
        if other_admins == 0:
            raise ValidationError(detail="cannot demote yourself — no other admins remain")

    user.is_admin = body.is_admin
    await db.flush()
    await log_admin_action(
        db, actor=admin.user, action="user.toggle_admin",
        target_type="user", target_id=user.id,
        payload={"is_admin": body.is_admin, "email": user.email},
        request=request,
    )
    await db.commit()
    return {"user_id": user.id, "is_admin": user.is_admin}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    admin: AdminWriteDep,
    db: DbDep,
    request: Request,
) -> None:
    """GDPR Art. 17 forced erasure on behalf of the user. Reuses the
    same purge service /me/delete uses, plus an audit log entry that
    records who-purged-whom."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("user", user_id)
    if user.id == admin.user.id:
        raise ValidationError(detail="cannot delete your own account from /admin — use /me/delete")

    email = user.email
    await purge_user_data(db, user_id=user.id)
    await log_admin_action(
        db, actor=admin.user, action="user.delete",
        target_type="user", target_id=user_id,
        payload={"email": email},
        request=request,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# System health (cron heartbeats, DB row counts, redis stats)
# ---------------------------------------------------------------------------

class HealthRow(BaseModel):
    label: str
    value: str
    accent: str | None = None


class SystemHealthOut(BaseModel):
    rows: list[HealthRow]
    generated_at: str


@router.get("/system-health", response_model=SystemHealthOut)
async def system_health(_: AdminDep, db: DbDep) -> SystemHealthOut:
    """One-shot snapshot of moving-part health: row counts, recent
    cron output, redis presence count. Designed for the right rail of
    the admin page."""
    from app.core.redis import get_redis

    rows: list[HealthRow] = []
    now = datetime.now(UTC)

    # ── DB row counts ────────────────────────────────────────────────
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    project_count = (await db.execute(select(func.count(Project.id)))).scalar_one()
    session_count = (await db.execute(select(func.count(SessionModel.id)))).scalar_one()
    audit_count = (await db.execute(select(func.count(AdminAuditLog.id)))).scalar_one()
    stripe_event_count = (await db.execute(select(func.count(StripeEvent.id)))).scalar_one()
    rows.append(HealthRow(label="users", value=str(user_count)))
    rows.append(HealthRow(label="projects", value=str(project_count)))
    rows.append(HealthRow(label="sessions", value=str(session_count)))
    rows.append(HealthRow(label="stripe events", value=str(stripe_event_count)))
    rows.append(HealthRow(label="admin actions", value=str(audit_count)))

    # ── Most recent github-sourced session = commit_sync heartbeat ───
    latest_github = (
        await db.execute(
            select(SessionModel.started_at)
            .where(SessionModel.source == "github")
            .order_by(desc(SessionModel.started_at)).limit(1)
        )
    ).scalar_one_or_none()
    if latest_github:
        age = now - latest_github
        rows.append(HealthRow(
            label="commit_sync",
            value=_humanize(age) + " ago",
            accent="green" if age < timedelta(minutes=15) else "amber",
        ))
    else:
        rows.append(HealthRow(label="commit_sync", value="never run", accent="amber"))

    # ── Redis ping ────────────────────────────────────────────────────
    try:
        r = await get_redis()
        await r.ping()
        info = await r.info("memory")
        used = info.get("used_memory_human", "?") if isinstance(info, dict) else "?"
        keys = await r.dbsize()
        rows.append(HealthRow(label="redis", value=f"{keys} keys · {used}", accent="green"))
    except Exception as exc:
        rows.append(HealthRow(label="redis", value=f"down: {exc}"[:120], accent="red"))

    # ── Stripe configured? ───────────────────────────────────────────
    rows.append(HealthRow(
        label="stripe",
        value="configured" if get_settings().stripe_secret_key else "not configured",
        accent="green" if get_settings().stripe_secret_key else "amber",
    ))

    return SystemHealthOut(rows=rows, generated_at=now.isoformat())


def _humanize(delta: timedelta) -> str:
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


# ---------------------------------------------------------------------------
# Usage metrics (DAU / WAU / MAU)
# ---------------------------------------------------------------------------

class UsageOut(BaseModel):
    dau: int
    wau: int
    mau: int
    active_now: int  # last 5 min
    sessions_today: int
    ships_today: int


@router.get("/usage-metrics", response_model=UsageOut)
async def usage_metrics(_: AdminDep, db: DbDep) -> UsageOut:
    """Active-user counts derived from session activity. DAU = users
    with >=1 session in last 24h; WAU = last 7 days; MAU = last 30."""
    now = datetime.now(UTC)
    last_5m = now - timedelta(minutes=5)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Distinct users active in each window — by joining sessions →
    # projects → workspaces → users.
    async def _distinct_active(since: datetime) -> int:
        return int((await db.execute(
            select(func.count(func.distinct(Workspace.owner_id)))
            .select_from(SessionModel)
            .join(Project, Project.id == SessionModel.project_id)
            .join(Workspace, Workspace.id == Project.workspace_id)
            .where(SessionModel.started_at >= since)
        )).scalar_one())

    active_now = await _distinct_active(last_5m)
    dau = await _distinct_active(last_24h)
    wau = await _distinct_active(last_7d)
    mau = await _distinct_active(last_30d)

    sessions_today = int((await db.execute(
        select(func.count(SessionModel.id)).where(SessionModel.started_at >= today_start)
    )).scalar_one())
    ships_today = int((await db.execute(
        select(func.count(Ship.id)).where(Ship.shipped_at >= today_start)
    )).scalar_one())

    return UsageOut(
        dau=dau, wau=wau, mau=mau, active_now=active_now,
        sessions_today=sessions_today, ships_today=ships_today,
    )


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
