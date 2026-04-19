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
