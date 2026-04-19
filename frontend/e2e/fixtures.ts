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
