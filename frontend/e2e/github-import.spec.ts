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

// Keep BACKEND referenced so lint won't complain if later scenarios need it.
void BACKEND;
