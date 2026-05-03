# backend/app/main.py
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

# Sentry init MUST happen before importing the FastAPI app, otherwise the
# instrumentation patches don't catch anything. The `if dsn:` guard means
# the SDK is a no-op until SENTRY_DSN_BACKEND is set in /etc/hangar/hangar.env.
_sentry_dsn = os.environ.get("SENTRY_DSN_BACKEND")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[SqlalchemyIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
        environment=os.environ.get("ENVIRONMENT", "production"),
        release=os.environ.get("GIT_SHA", "unknown"),
        # Don't auto-capture session-cookie / authorization headers
        send_default_pii=False,
    )
    logging.getLogger(__name__).info("Sentry initialised — release=%s", os.environ.get("GIT_SHA", "unknown"))

# Activity timeline
from app.api.v1.activity import router as activity_router

# Spec-6 admin dashboard + 2FA
from app.api.v1.admin import router as admin_router

# BYOK AI features
from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router

# Spec 4 — Launch-Enabler
from app.api.v1.billing import router as billing_router
from app.api.v1.cli import router as cli_router
from app.api.v1.connections import router as connections_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.dev import router as dev_router

# Live project events (SSE stream)
from app.api.v1.events import router as events_router
from app.api.v1.github_repos import router as github_repos_router
from app.api.v1.groups import router as groups_router

# Spec 5A — Auto-Signals
from app.api.v1.health import router as health_router
from app.api.v1.ideas import router as ideas_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.launches import router as launches_router
from app.api.v1.lifecycle import router as lifecycle_router
from app.api.v1.me import router as me_router
from app.api.v1.notes import router as notes_router
from app.api.v1.passkey import router as passkey_router

# Spec 5B — Portfolio-Intel
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.project_children import router as project_children_router
from app.api.v1.projects import router as projects_router
from app.api.v1.screenshots import preview_router as screenshots_preview_router

# Visual previews — live-preview + ship-shot timeline
from app.api.v1.screenshots import router as screenshots_router
from app.api.v1.search import router as search_router
from app.api.v1.secrets import router as secrets_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.ships import router as ships_router
from app.api.v1.stack_items import router as stack_items_router

# Spec-6 C4 — Public status endpoint
from app.api.v1.status import router as status_router
from app.api.v1.tags import router as tags_router

# Per-project TODOs
from app.api.v1.todos import router as todos_router
from app.api.v1.two_factor import router as two_factor_router
from app.api.v1.workspaces import router as workspaces_router
from app.core.audit import install_audit_listener
from app.core.middleware import install_session_middleware
from app.core.plan_gate_middleware import install_plan_gate_middleware
from app.core.problem import install_problem_handler
from app.jobs.commit_sync import schedule_commit_sync_jobs
from app.jobs.health_cron import schedule_health_jobs
from app.jobs.oauth_cleanup import refresh_active_connections_gauge
from app.jobs.oauth_cleanup import run_once as oauth_cleanup_run_once
from app.jobs.screenshot_cron import schedule_screenshot_jobs
from app.jobs.trial_lifecycle import schedule_trial_lifecycle_job
from app.mcp.server import router as mcp_router
from app.metrics.endpoint import router as metrics_router
from app.oauth.discovery import router as oauth_discovery_router
from app.oauth.server import router as oauth_server_router

_scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _scheduler.add_job(
        oauth_cleanup_run_once,
        "cron",
        hour=3,
        minute=15,
        id="oauth_cleanup",
    )
    _scheduler.add_job(
        refresh_active_connections_gauge,
        "interval",
        seconds=60,
        id="active_conn_gauge",
    )
    # Spec 5A — Auto-Signals: health probes every 5 min
    schedule_health_jobs(_scheduler)
    # Visual previews — hourly project-wide refresh
    schedule_screenshot_jobs(_scheduler)
    # Commit sync — safety net that logs session rows from GitHub commits
    # every 10 min, regardless of whether Claude called vibecell_log_session
    # or not. Keeps dashboards accurate even when the SKILL rule is missed.
    schedule_commit_sync_jobs(_scheduler)
    # Spec-6 trial lifecycle — hourly state machine. Replaces the old
    # daily trial_warning_job; this one also flips status to past_due
    # when trial_ends_at passes (the old job left it at "trialing"
    # forever).
    schedule_trial_lifecycle_job(_scheduler)
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(
    title="Vibecell",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)

install_problem_handler(app)
# Order: middleware added LAST runs FIRST. We need SessionMiddleware to run
# before PlanGateMiddleware (so request.state.user_id is set when PlanGate
# checks it) → install plan_gate FIRST, session SECOND.
install_plan_gate_middleware(app)
install_session_middleware(app)
install_audit_listener()

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(workspaces_router)
app.include_router(projects_router)
app.include_router(project_children_router)
app.include_router(secrets_router)
app.include_router(groups_router)
app.include_router(stack_items_router)
app.include_router(tags_router)
app.include_router(integrations_router)
app.include_router(github_repos_router)
app.include_router(cli_router)
app.include_router(dev_router)
# Spec 2 — Ship Loop
app.include_router(sessions_router)
app.include_router(decisions_router)
app.include_router(ideas_router)
app.include_router(ships_router)
app.include_router(launches_router)
app.include_router(lifecycle_router)
app.include_router(notes_router)
app.include_router(search_router)
# Spec 3 — OAuth / MCP
app.include_router(oauth_discovery_router)
app.include_router(oauth_server_router)
app.include_router(mcp_router)
# Spec 3.2 — Connections (unified oauth + cli list/revoke)
app.include_router(connections_router)
# Spec 3.5 — Observability
app.include_router(metrics_router)
# Spec 4 — Launch-Enabler
app.include_router(billing_router)
app.include_router(passkey_router)
# Spec 5A — Auto-Signals
app.include_router(health_router)
# Spec-6 C4 — Public status endpoint
app.include_router(status_router)
# Spec-6 admin dashboard + 2FA (gated by require_admin / require_admin_2fa)
app.include_router(two_factor_router)
app.include_router(admin_router)
# Spec 5B — Portfolio-Intel
app.include_router(portfolio_router)
# Activity timeline
app.include_router(activity_router)
# Visual previews
app.include_router(screenshots_router)
app.include_router(screenshots_preview_router)
# Live project-event stream (SSE)
app.include_router(events_router)
# Per-project TODOs
app.include_router(todos_router)
# BYOK AI features
app.include_router(ai_router)


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
