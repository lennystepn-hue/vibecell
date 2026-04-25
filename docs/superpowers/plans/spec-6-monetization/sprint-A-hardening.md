# Sprint A — Hardening (Pre-Monetization Foundation)

> **Goal:** Make Vibecell safe to charge real money for. Email-flows, GDPR, observability, real rate-limits.

**Estimated time:** 5 working days (~30 hours)

**Pre-flight check:**
- Spec 1 + 3.5 are deployed and green.
- Production has a working backup of `hangar-postgres` (manual `pg_dump` at minimum) before starting.
- Resend domain `vibecell.dev` is verified and `RESEND_API_KEY` is in `/etc/hangar/hangar.env`.

---

## Phase A1 — Email Verification (DRASTICALLY REDUCED — see audit)

> **2026-04-25 audit finding:** Magic-link auth already proves email ownership.
> Decision doc: [`docs/superpowers/decisions/2026-04-25-email-verification-already-implicit.md`](../../decisions/2026-04-25-email-verification-already-implicit.md).
> Original 8-step plan replaced with: add column + set on verify + backfill.
> Time savings: ~4 hours.

**Why:** Stripe and downstream tooling need a single source of truth for "is this user's email confirmed". Magic-link already confirms it; we just need to **record** that fact.

**Files:**
- Modify: `backend/app/models/user.py` (add `email_verified_at: Mapped[datetime | None]`)
- Migration: `backend/alembic/versions/0015_user_email_verified_at.py`
- Modify: `backend/app/services/login.py::verify_magic_link` (set the field)
- Test: `backend/tests/integration/test_email_verified_at.py`

- [ ] **Step 1: Migration — add column + backfill**

```python
# 0015_user_email_verified_at.py
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill: every existing user logged in via magic-link, so their email
    # was verified at account-creation time. Use User.created_at as the proxy.
    op.execute('UPDATE "user" SET email_verified_at = created_at WHERE email_verified_at IS NULL')

def downgrade() -> None:
    op.drop_column("user", "email_verified_at")
```

- [ ] **Step 2: Add column to User model**

```python
# backend/app/models/user.py — inside class User(Base):
email_verified_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

- [ ] **Step 3: Set on first verify**

In `backend/app/services/login.py::verify_magic_link`, after `token.consumed_at = datetime.now(UTC)`:

```python
if user.email_verified_at is None:
    user.email_verified_at = datetime.now(UTC)
```

(Idempotent — only writes the first time.)

- [ ] **Step 4: Integration test**

```python
# backend/tests/integration/test_email_verified_at.py
async def test_first_magic_link_sets_email_verified_at(session):
    raw = await issue_magic_link(session, email="test@example.com")
    await session.commit()
    await verify_magic_link(session, raw_token=raw)
    await session.commit()
    user = (await session.execute(
        select(User).where(User.email == "test@example.com")
    )).scalar_one()
    assert user.email_verified_at is not None

async def test_second_verify_does_not_reset_timestamp(session):
    # ...sign up, capture timestamp t1, sign in again, assert == t1
```

Run: `uv run pytest backend/tests/integration/test_email_verified_at.py -v`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/0015_*.py \
    backend/app/services/login.py backend/tests/integration/test_email_verified_at.py
git commit -m "feat(auth): record email_verified_at when magic-link is consumed"
```

---

## Phase A2 — Password Reset

**Why:** When we add Stripe-backed password auth later (or when users want to log in without waiting for magic-link mail), reset is non-negotiable. Even today: a user who loses access to their inbox can't recover their account.

**Note:** Today Vibecell uses magic-link auth only — no passwords. So "password reset" is really "fallback magic-link delivery / change primary email". Decision in Step 1 below.

**Files:**
- Decision-doc step (no code) followed by either:
  - **Path A** (just email-change): `backend/app/routes/email_change.py` + matching migration + UI
  - **Path B** (full password auth): much bigger — defer to a later spec

- [ ] **Step 1: Decide which path (15-min spike, document in `docs/superpowers/decisions/2026-XX-password-reset.md`)**

Recommendation: **Path A** for Sprint A. We don't need passwords; we need a way to change the email on file. Keep magic-link as the only auth method.

- [ ] **Step 2: (Path A) Email-change endpoint**

```python
# /me/change-email — issues a one-time token to the *new* email.
# /me/change-email/confirm?token=... — verifies, swaps user.email.
```

Same token-table pattern as A1 (reuse `email_verification_token` with a `kind` column: `"verify_signup"` or `"change_email"`).

- [ ] **Step 3: Migration to add `kind` column**

```python
# 0016_email_token_kind.py
op.add_column("email_verification_token", sa.Column("kind", sa.String(16), server_default="verify_signup", nullable=False))
op.add_column("email_verification_token", sa.Column("payload_json", sa.JSON(), nullable=True))  # holds new_email for change-email flow
```

- [ ] **Step 4: Frontend**

`/settings/email` page with current email + "change email" button → modal → input new email → confirmation banner "we sent a link to <new>". Existing settings page (`Spec 1 Phase 15`) gets a new tab.

- [ ] **Step 5: Test + commit**

```python
async def test_change_email_round_trip(...): ...
```

```bash
git commit -m "feat(auth): email-change flow with confirmation token"
```

---

## Phase A3 — Account Delete + GDPR Data Export

**Why:** EU law. Without these endpoints, German/EU paying users can demand deletion via support email and we have no automated path → manual SQL each time → liability.

**Files:**
- Create: `backend/app/routes/account.py` (`/me/export`, `/me`, DELETE)
- Create: `backend/app/services/account_purge.py`
- Frontend: `frontend/src/pages/SettingsAccount.vue` (delete + export buttons)
- Test: `backend/tests/integration/test_account_lifecycle.py`

- [ ] **Step 1: Export endpoint**

```python
@router.get("/me/export")
async def export_my_data(current_user: UserDep, session: SessionDep):
    """Stream a JSON dump of every row owned by the user across every table.
    GDPR Art. 20 (data portability). Synchronous for now — async-job if it gets slow."""
    user_data = await account_purge.gather_user_data(session, current_user.id)
    return StreamingResponse(
        json_lines(user_data),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=vibecell-export-{current_user.id}.json"},
    )
```

`gather_user_data` walks: User, Workspace memberships, Project, ProjectContext, Repo, Environment, Infra, Link, Command, Stack, Tag, McpAuditLog, Session, Ship, ProjectTodo, Decision, Idea, EmailVerificationToken, Subscription (after Sprint B). One dict per table, list of rows.

- [ ] **Step 2: Delete endpoint**

```python
@router.delete("/me")
async def delete_account(
    confirmation: str,  # body: must equal user's email
    current_user: UserDep,
    session: SessionDep,
):
    if confirmation != current_user.email:
        raise HTTPException(400, "confirmation must match your email")
    await account_purge.purge(session, current_user.id)
    await session.commit()
    return {"ok": True}
```

`purge` cascades through all `ondelete=CASCADE` FKs + nukes the keychain entry + (Sprint B) cancels any active Stripe subscription.

- [ ] **Step 3: Frontend `/settings/account` page**

Two buttons:
1. "Download my data" → `GET /me/export` triggers download.
2. "Delete my account" → modal demanding email-confirmation typed in → `DELETE /me`.

Both buttons live in a `border-red-500/30` "danger zone" card.

- [ ] **Step 4: Integration test**

```python
async def test_export_then_delete(client, db, authed_user):
    # create some data
    await client.post("/projects", json={"name": "test", "slug": "test"})
    # export
    resp = await client.get("/me/export")
    assert resp.status_code == 200
    payload = json.loads(resp.content)
    assert any(p["slug"] == "test" for p in payload["projects"])
    # delete
    resp = await client.delete("/me", json={"confirmation": authed_user.email})
    assert resp.status_code == 200
    # verify gone
    user = await db.get(User, authed_user.id)
    assert user is None
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(account): GDPR data export + account delete"
```

---

## Phase A4 — Postgres Backup Cron + Restore Drill

**Why:** `known_issue` says "no PG-backup regime". A paying user's data MUST survive a disk failure. Daily backups + a tested restore path.

**Files:**
- Already exists: `ops/backup.sh` (per Vibecell `commands` — labeled `backup-db`)
- Audit + harden it
- Create: `ops/restore-drill.sh`
- Modify: `ops/docker-compose.yml` (add `pg-backup` service running cron)
- Doc: `docs/runbooks/backup-restore.md`

- [ ] **Step 1: Audit existing `ops/backup.sh`**

Read it. Confirm it does `pg_dump` to a timestamped file. If it doesn't push to off-server storage, add S3/Backblaze upload (use `rclone` or `aws s3 cp`).

- [ ] **Step 2: Daily cron via Docker container**

Add to `ops/docker-compose.yml`:

```yaml
pg-backup:
  image: prodrigestivill/postgres-backup-local:16
  restart: unless-stopped
  depends_on: [postgres]
  environment:
    POSTGRES_HOST: postgres
    POSTGRES_DB: hangar
    POSTGRES_USER: hangar
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_EXTRA_OPTS: '-Z6 --schema=public'
    SCHEDULE: '@daily'
    BACKUP_KEEP_DAYS: 7
    BACKUP_KEEP_WEEKS: 4
    BACKUP_KEEP_MONTHS: 6
  volumes:
    - /srv/hangar/backups:/backups
```

Then daily `rsync` `/srv/hangar/backups` to off-server storage (Backblaze B2 — cheapest, no AWS lock-in).

- [ ] **Step 3: Restore-drill script**

```bash
#!/bin/bash
# ops/restore-drill.sh - run monthly. Spins up a throwaway postgres, restores
# the latest backup into it, asserts row counts match production.
set -e
LATEST=$(ls -t /srv/hangar/backups/*.sql.gz | head -1)
docker run --rm -d --name pg-drill -e POSTGRES_PASSWORD=test postgres:16-alpine
sleep 5
gunzip -c "$LATEST" | docker exec -i pg-drill psql -U postgres
ROWS=$(docker exec pg-drill psql -U postgres -tc "select count(*) from public.user")
[ "$ROWS" -gt 0 ] || { echo "DRILL FAILED: zero users"; exit 1; }
docker stop pg-drill
echo "ok restore drill passed: $ROWS users in latest backup"
```

Add to crontab: `0 4 1 * * /srv/hangar/ops/restore-drill.sh >> /var/log/restore-drill.log 2>&1`

- [ ] **Step 4: Runbook**

`docs/runbooks/backup-restore.md` with copy-paste commands for the on-call to restore from B2 in <30 min.

- [ ] **Step 5: Test the drill once manually, commit**

```bash
ssh root@89.167.111.89 /srv/hangar/ops/restore-drill.sh
# expect: "ok restore drill passed: N users in latest backup"
git add ops/ docs/runbooks/backup-restore.md
git commit -m "ops: daily PG backups to B2 + monthly restore drill"
```

---

## Phase A5 — Sentry Integration

**Why:** Today we deploy and pray. A 500 in production goes to nginx logs nobody reads. Paid customers expect us to know about errors before they tell us.

**Files:**
- Modify: `backend/app/main.py` (sentry_sdk init)
- Modify: `frontend/src/main.ts` (Sentry-Vue init)
- Modify: `backend/pyproject.toml` (sentry-sdk dep)
- Modify: `frontend/package.json` (@sentry/vue)
- Add to `/etc/hangar/hangar.env`: `SENTRY_DSN_BACKEND`, `SENTRY_DSN_FRONTEND`
- Doc: `docs/runbooks/observability.md`

- [ ] **Step 1: Create Sentry account + projects (one-time, manual)**

Sentry.io free tier handles 5k events/month — plenty for v1. Create two projects: `vibecell-backend` (Python) and `vibecell-frontend` (Vue). Get both DSNs.

- [ ] **Step 2: Backend init**

```python
# backend/app/main.py top of create_app()
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

if dsn := os.environ.get("SENTRY_DSN_BACKEND"):
    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,  # 10% of requests
        environment=os.environ.get("ENVIRONMENT", "production"),
        release=os.environ.get("GIT_SHA", "unknown"),
    )
```

- [ ] **Step 3: Frontend init**

```typescript
// frontend/src/main.ts before app.mount
import * as Sentry from "@sentry/vue";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    app,
    dsn: import.meta.env.VITE_SENTRY_DSN,
    tracesSampleRate: 0.1,
    environment: import.meta.env.MODE,
  });
}
```

- [ ] **Step 4: Wire `GIT_SHA` into the deploy**

`ops/deploy.sh` already has `SHA=$(git rev-parse --short HEAD)`. Pass it as build-arg AND container env:

```bash
docker compose build --build-arg GIT_SHA=$SHA
GIT_SHA=$SHA docker compose up -d
```

- [ ] **Step 5: Trigger a test error from staging, verify it lands in Sentry**

Add a debug endpoint behind `ENVIRONMENT == "staging"`: `GET /debug/throw` raises `RuntimeError("sentry test")`. Hit it, confirm Sentry caught it. Remove the endpoint before commit.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(observability): Sentry integration (backend + frontend)"
```

---

## Phase A6 — Wire Rate-Limits Into Endpoints

**Why:** `known_issue`: `test_register_rate_limit skipped — rate-limit not wired`. Without rate-limits, a single bad actor can drain Anthropic credits via repeated enrichment calls and DOS the magic-link endpoint into Resend's spam-rep penalty box.

**Files:**
- Modify: `backend/app/middleware/rate_limit.py` (already exists but unused)
- Modify: `backend/app/routes/auth.py` (decorate magic-link endpoint)
- Modify: `backend/app/routes/projects.py` (decorate enrichment trigger)
- Modify: `backend/app/routes/email_verify.py` (decorate resend endpoint)
- Test: `backend/tests/integration/test_register_rate_limit.py` (un-skip)

- [ ] **Step 1: Audit `app/middleware/rate_limit.py`**

It exists from Spec 1 Phase 2 but isn't applied anywhere. Confirm Redis-backed sliding window is in place.

- [ ] **Step 2: Apply rate-limit dependencies**

```python
# magic-link: 5 requests / hour / IP
@router.post("/auth/magic-link", dependencies=[Depends(rate_limit("ip", 5, 3600))])
# enrichment: 20 requests / hour / user
@router.post("/projects/{slug}/enrich", dependencies=[Depends(rate_limit("user", 20, 3600))])
# resend verification: 3 / hour / user
@router.post("/auth/verify-email/resend", dependencies=[Depends(rate_limit("user", 3, 3600))])
```

- [ ] **Step 3: Un-skip the test**

```python
# backend/tests/integration/test_register_rate_limit.py
# remove @pytest.mark.skip
async def test_magic_link_rate_limit(client):
    for _ in range(5):
        await client.post("/auth/magic-link", json={"email": "x@y.z"})
    resp = await client.post("/auth/magic-link", json={"email": "x@y.z"})
    assert resp.status_code == 429
```

- [ ] **Step 4: Update Vibecell `known_issues`**

After commit, call `vibecell_resolve_known_issue` with needle `"rate-limit nicht im endpoint wired"`.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(security): wire rate-limits into auth + enrichment endpoints"
```

---

## Sprint A Done-Definition

- [ ] All 6 phases committed and deployed
- [ ] CI green on `main`
- [ ] Restore-drill ran successfully once
- [ ] Sentry has caught at least one real (or seeded) event
- [ ] Vibecell known-issue "rate-limit nicht im endpoint wired" resolved
- [ ] Tag the release: `git tag v0.6.A-hardening && git push --tags`
- [ ] Pricing decision (Option 1 vs Option 2) locked — write into Vibecell `decision`
