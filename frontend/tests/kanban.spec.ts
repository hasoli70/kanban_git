import { expect, test } from "@playwright/test";
import { loginAsTestUser } from "./helpers";

test.beforeEach(async ({ page }) => {
  await loginAsTestUser(page);
});

test("loads the kanban board", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card and persists it across page reload", async ({ page }) => {
  const title = `E2E ${Date.now()}`;
  const firstColumn = page.locator('[data-testid^="column-"]').first();

  // Add
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill(title);
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText(title)).toBeVisible();

  // Reload -> the card must still be there (persisted to DB via PUT /api/board)
  await page.reload();
  const refreshedColumn = page.locator('[data-testid^="column-"]').first();
  await expect(refreshedColumn.getByText(title)).toBeVisible({ timeout: 10_000 });

  // Cleanup so re-runs don't accumulate state in the shared dev DB
  await refreshedColumn
    .getByRole("button", { name: new RegExp(`delete ${title}`, "i") })
    .click();
  await expect(refreshedColumn.getByText(title)).not.toBeVisible();
});
