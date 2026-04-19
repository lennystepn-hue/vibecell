# Vibecell Frontend

Vue 3 + TS + Vite + Pinia.

## Dev

```bash
pnpm install
pnpm dev
```

Opens http://localhost:3000 with `/api` proxied to backend at :8000.

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
