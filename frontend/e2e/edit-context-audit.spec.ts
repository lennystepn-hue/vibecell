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
