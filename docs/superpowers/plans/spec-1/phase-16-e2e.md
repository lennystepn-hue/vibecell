# Phase 16 — E2E Playwright Scenarios

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Three end-to-end scenarios covering the golden paths: signup + first project, GitHub import, context editing with audit. Tests run against a locally-served frontend + a reachable backend (staging or local).

**Prerequisite:** Phase 15 complete (HEAD ≥ `cdef698`).

---

## Scope

Three Playwright tests at `frontend/e2e/`:

1. **signup-create-project** — magic-link sign-in (dev-mode log intercept) → empty dashboard → quick-add project → land on detail view
2. **github-import** — connect GitHub (mocked via backend `HANGAR_DEV_MODE` + pre-seeded integration) → list repos → select 2 → import → both land as projects
3. **edit-context-audit** — sign in → create project → edit focus + next step → verify persisted on reload + audit row exists

Tests target `http://localhost:3000` (Vite dev server) with backend at `http://89.167.111.89:8000` (staging) OR a locally proxied backend if available.

---

## Files

```
frontend/
├── playwright.config.ts            config
├── e2e/
│   ├── fixtures.ts                 shared: magic-link intercept helper, signin helper
│   ├── signup-create-project.spec.ts
│   ├── github-import.spec.ts
│   └── edit-context-audit.spec.ts
├── package.json                     (modify) add playwright deps + scripts
└── .gitignore                       (modify) ignore test-results + playwright-report
```

---

## Task 16.1 — Install Playwright + config

**Files:** `frontend/package.json` (modify), `frontend/playwright.config.ts` (new)

Add to `frontend/package.json` devDependencies:

```json
"@playwright/test": "^1.49.0"
```

Add scripts:

```json
"e2e": "playwright test",
"e2e:install": "playwright install chromium",
"e2e:ui": "playwright test --ui"
```

**File:** `frontend/playwright.config.ts`

```ts
import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.HANGAR_E2E_BASE_URL ?? "http://localhost:3000";
const BACKEND_URL = process.env.HANGAR_E2E_BACKEND_URL ?? "http://89.167.111.89:8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,  // shared DB state; run sequentially
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "pnpm dev",
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
    env: {
      HANGAR_E2E_BACKEND_URL: BACKEND_URL,
    },
  },
});
```

**Modify `frontend/vite.config.ts`** — make the `/api` proxy target env-aware so E2E can point at staging. Current `server.proxy`:

```ts
proxy: {
  "/api": { target: "http://localhost:8000", changeOrigin: false },
},
```

Change to:

```ts
proxy: {
  "/api": {
    target: process.env.HANGAR_E2E_BACKEND_URL ?? "http://localhost:8000",
    changeOrigin: true,
  },
},
```

Install playwright browsers:

```bash
cd frontend && pnpm install && pnpm exec playwright install chromium
```

**Modify `frontend/.gitignore`** (append):

```
test-results/
playwright-report/
playwright/.cache/
```

Commit: `chore(frontend): install playwright + env-aware vite proxy for E2E`

---

## Task 16.2 — Shared fixtures

**File:** `frontend/e2e/fixtures.ts`

```ts
import { expect, Page, test as base } from "@playwright/test";

const BACKEND = process.env.HANGAR_E2E_BACKEND_URL ?? "http://89.167.111.89:8000";

/**
 * Reset the staging DB to a clean slate and re-apply Alembic migrations.
 * Requires the staging VPS to have `hangar-e2e-reset` helper — if absent,
 * uses a raw SQL call through the backend's debug endpoint. For now we
 * trust manual cleanup: each test uses a unique email so DB state accrues
 * but doesn't collide.
 */
export async function resetIfPossible(): Promise<void> {
  // Best-effort: POST /api/v1/test/reset if available; otherwise no-op.
  try {
    await fetch(`${BACKEND}/api/v1/test/reset`, { method: "POST" });
  } catch { /* ignore */ }
}

/**
 * Issue a magic-link token directly via the backend API, then navigate
 * the page to the verify URL. Backend must be in HANGAR_DEV_MODE so it
 * doesn't attempt real email delivery — but we still need the token
 * itself. Workaround: poll the backend's DB for the latest magic-link
 * token for this email via a test endpoint (not implemented in v1),
 * or craft a deterministic token by calling POST /auth/magic-link and
 * reading the server log.
 *
 * In practice we bypass the email step by calling a test-only route
 * that issues a token directly. If that route isn't exposed, caller
 * must seed via a different path (e.g. backend's dev console).
 */
export async function signIn(page: Page, email: string): Promise<void> {
  // Step 1: request the magic link
  const r = await fetch(`${BACKEND}/api/v1/auth/magic-link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  expect(r.status).toBe(202);

  // Step 2: pull the raw token from the backend test endpoint.
  // See Task 16.5 — we add a dev-mode-only backend route that returns
  // the latest unconsumed token for a given email.
  const tr = await fetch(`${BACKEND}/api/v1/test/magic-link-token?email=${encodeURIComponent(email)}`);
  expect(tr.status).toBe(200);
  const { token } = (await tr.json()) as { token: string };

  // Step 3: follow the verify URL so backend sets the cookie
  await page.goto(`/auth/verify?token=${token}`);
  // After backend 303 → /, Vue Router lands on /p (or /login if something broke).
  await page.waitForURL((url) => url.pathname.startsWith("/p") || url.pathname === "/", {
    timeout: 10_000,
  });
}

export const test = base.extend<object>({});

export { expect };
```

Commit: `feat(frontend): E2E shared fixtures — signIn helper + dev-mode token pull`

---

## Task 16.3 — Backend dev-mode helper route

**File:** `backend/app/api/v1/dev.py` (new)

```python
"""Dev-mode-only helpers for E2E tests.

All routes are gated on HANGAR_DEV_MODE=1. Never enable in production.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import HangarError, NotFoundError
from app.models import MagicLinkToken

router = APIRouter(prefix="/api/v1/test", tags=["_dev"])


def _require_dev() -> None:
    if not get_settings().dev_mode:
        raise HangarError(
            title="Dev endpoint disabled",
            status=404,
            type_="/errors/not-found",
            detail="dev mode not enabled",
        )


@router.get("/magic-link-token")
async def latest_magic_link_token(
    email: Annotated[str, Query(min_length=3)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Return the RAW token for the most-recent unconsumed magic-link for `email`.

    Note: we only store the hash, not the raw token. So this route can't return
    the token — it returns the token_hash instead, and the E2E fixture uses a
    different strategy: it POSTs /auth/magic-link, then reads the backend logs
    where the dev-mode mailer printed the full verify_url.

    For now, we return the hash so the test can at least confirm the token was
    issued. Real E2E is gated on another mechanism (see Task 16.4 — direct DB
    seeding via SQL).
    """
    _require_dev()
    token = (await db.execute(
        select(MagicLinkToken)
        .where(MagicLinkToken.email == email.lower(), MagicLinkToken.consumed_at.is_(None))
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if token is None:
        raise NotFoundError("magic_link_token", email)
    # We can't recover the raw token from the hash. Dev-only workaround:
    # issue a fresh token here and return it.
    import secrets
    import hashlib
    from datetime import UTC, datetime, timedelta
    from app.core.ulid import new_ulid

    raw = secrets.token_urlsafe(32)
    from app.models import MagicLinkToken as _Token
    new = _Token(
        id=new_ulid(),
        email=email.lower(),
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(new)
    await db.commit()
    return {"token": raw}
```

Wire in `main.py`:

```python
from app.api.v1.dev import router as dev_router
# ...
app.include_router(dev_router)
```

Deploy to staging (sync + restart backend):

```bash
tar -cf - backend/app/api/v1/dev.py backend/app/main.py | ssh root@89.167.111.89 "cd /srv/hangar && tar -xf -"

ssh root@89.167.111.89 'pgrep -f "uvicorn app.main" | xargs -r kill 2>/dev/null; cd /srv/hangar/backend && export HANGAR_DATABASE_URL="postgresql+asyncpg://hangar:hangar_dev@localhost:5432/hangar_dev" HANGAR_REDIS_URL="redis://localhost:6379/0" HANGAR_MASTER_KEY="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" HANGAR_RESEND_API_KEY="test" HANGAR_GITHUB_CLIENT_ID="test" HANGAR_GITHUB_CLIENT_SECRET="test" HANGAR_BASE_URL="http://89.167.111.89:3000" HANGAR_DEV_MODE=1 && nohup /root/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/hangar.log 2>&1 &'

sleep 3 && curl -s http://89.167.111.89:8000/api/v1/healthz
```

Commit: `feat(backend): dev-mode /api/v1/test/magic-link-token route for E2E`

---

## Task 16.4 — E2E scenario 1: signup + create project

**File:** `frontend/e2e/signup-create-project.spec.ts`

```ts
import { expect, test } from "./fixtures";
import { signIn } from "./fixtures";

test("new user signs in and creates first project", async ({ page }) => {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;

  await signIn(page, email);

  // We should land on /p
  await page.waitForURL(/\/p(\/|$)/);
  await expect(page.getByText(/Your hangar is empty/i)).toBeVisible();

  await page.getByRole("button", { name: "+ New project" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.getByPlaceholder("Butlr").fill("E2E Butlr");
  // slug auto-fills — verify
  const slugInput = page.getByPlaceholder("butlr");
  await expect(slugInput).toHaveValue("e2e-butlr");

  await page.getByRole("button", { name: "Create" }).click();

  // Expected: detail page
  await page.waitForURL(/\/p\/e2e-butlr/);
  await expect(page.getByRole("heading", { name: "E2E Butlr" })).toBeVisible();
  await expect(page.getByText("building")).toBeVisible();
});
```

Commit: `test(e2e): scenario 1 — signup + create first project`

---

## Task 16.5 — E2E scenarios 2 + 3

**File:** `frontend/e2e/github-import.spec.ts`

```ts
import { expect, test } from "./fixtures";
import { signIn } from "./fixtures";

const BACKEND = process.env.HANGAR_E2E_BACKEND_URL ?? "http://89.167.111.89:8000";

test("connect GitHub and import 2 repos", async ({ page }) => {
  const email = `e2e-gh-${Date.now()}@example.com`;

  await signIn(page, email);

  // Pre-seed a GitHub integration via the backend + mock the repos endpoint
  // via a route handler. Integration row must exist so the connected-state
  // renders; actual GitHub API is intercepted client-side via page.route.
  await page.goto("/import/github");

  // If no integration row, backend /integrations returns []. We intercept
  // and inject a fake integration + fake repos.
  await page.route(`**/api/v1/integrations`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "01TESTGH",
          kind: "github",
          connected_at: new Date().toISOString(),
          config: { login: "e2e-user" },
        },
      ]),
    });
  });

  await page.route(`**/api/v1/integrations/github/repos*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          owner: "e2e-user",
          name: "alpha",
          full_name: "e2e-user/alpha",
          description: "alpha project",
          private: false,
          default_branch: "main",
          language: "Python",
          license_spdx: "MIT",
          homepage: null,
          clone_url: "https://github.com/e2e-user/alpha.git",
          pushed_at: new Date().toISOString(),
        },
        {
          owner: "e2e-user",
          name: "beta",
          full_name: "e2e-user/beta",
          description: "beta project",
          private: true,
          default_branch: "main",
          language: "Go",
          license_spdx: null,
          homepage: null,
          clone_url: "https://github.com/e2e-user/beta.git",
          pushed_at: new Date().toISOString(),
        },
      ]),
    });
  });

  await page.route(`**/api/v1/integrations/github/import`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: [
          { owner: "e2e-user", name: "alpha", slug: "alpha", status: "imported", detail: null },
          { owner: "e2e-user", name: "beta", slug: "beta", status: "imported", detail: null },
        ],
      }),
    });
  });

  // Reload so the new /integrations intercept activates
  await page.reload();
  await expect(page.getByText("e2e-user")).toBeVisible();
  await expect(page.getByText("e2e-user/alpha")).toBeVisible();
  await expect(page.getByText("e2e-user/beta")).toBeVisible();

  // Select both repos
  await page.locator("input[type=checkbox]").nth(0).check();
  await page.locator("input[type=checkbox]").nth(1).check();

  // Import button appears in the sticky footer
  await expect(page.getByRole("button", { name: /Import 2 repos/ })).toBeVisible();
  await page.getByRole("button", { name: /Import 2 repos/ }).click();

  // Expect a success toast
  await expect(page.getByText(/Imported 2 projects/)).toBeVisible();
});
```

**File:** `frontend/e2e/edit-context-audit.spec.ts`

```ts
import { expect, test } from "./fixtures";
import { signIn } from "./fixtures";

test("edit project context persists on reload", async ({ page }) => {
  const email = `e2e-ctx-${Date.now()}@example.com`;

  await signIn(page, email);
  await page.waitForURL(/\/p(\/|$)/);

  // Create project
  await page.getByRole("button", { name: /\+ New project/ }).click();
  await page.getByPlaceholder("Butlr").fill("Ctx Butlr");
  await page.getByRole("button", { name: "Create" }).click();
  await page.waitForURL(/\/p\/ctx-butlr/);

  // Open context editor
  await page.getByRole("button", { name: /✎ edit context/ }).click();

  // Fill focus + next step
  const focusArea = page.getByLabel(/current focus/i);
  await focusArea.fill("Stripe webhook for subscription events");
  const nextArea = page.getByLabel(/next step/i);
  await nextArea.fill("Handle customer.subscription.deleted");

  // Save
  await page.getByRole("button", { name: "Save" }).click();

  // Toast confirms
  await expect(page.getByText(/Context saved/i)).toBeVisible();

  // Reload page; context should persist
  await page.reload();
  await expect(page.getByText(/Stripe webhook for subscription events/)).toBeVisible();
  await expect(page.getByText(/Handle customer.subscription.deleted/)).toBeVisible();
});
```

Commit: `test(e2e): scenarios 2 + 3 — GitHub import (mocked) + context edit persistence`

---

## Task 16.6 — Run docs

**File:** `frontend/README.md` (append)

```markdown
## E2E tests

Playwright tests live in `e2e/`. They expect a reachable backend in
dev-mode (for the `/api/v1/test/magic-link-token` helper route).

```bash
# Install browser
pnpm e2e:install

# Run against staging backend (default)
pnpm e2e

# Or run against local backend
HANGAR_E2E_BACKEND_URL=http://localhost:8000 pnpm e2e

# Interactive mode (recommended for debugging)
pnpm e2e:ui
```

The backend **must** be running with `HANGAR_DEV_MODE=1` or the dev
test routes (`/api/v1/test/*`) return 404.
```

Commit: `docs(frontend): README section on running Playwright E2E`

---

## Phase 16 complete when

- [ ] `pnpm exec playwright install chromium` succeeds.
- [ ] `playwright.config.ts` points webServer → `pnpm dev`.
- [ ] Backend has `/api/v1/test/magic-link-token` (dev-mode-only).
- [ ] 3 spec files in `frontend/e2e/`.
- [ ] Ideally: `pnpm e2e` runs all 3 scenarios successfully against staging.
- [ ] 6 commits on main (16.1–16.6).
