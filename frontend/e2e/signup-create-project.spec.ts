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
