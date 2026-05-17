import { expect, test } from "@playwright/test";
import { loginAsTestUser } from "./helpers";

const HAS_AI_KEY = Boolean(process.env.OPENROUTER_API_KEY);

test.describe("AI chat sidebar", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsTestUser(page);
  });

  test("opens and closes the sidebar", async ({ page }) => {
    await page.getByRole("button", { name: "Chat" }).click();
    const sidebar = page.getByRole("complementary", { name: /ai chat/i });
    await expect(sidebar).toBeVisible();
    await expect(sidebar.getByText(/ask me to add a card/i)).toBeVisible();

    await sidebar.getByRole("button", { name: /close chat/i }).click();
    await expect(sidebar).toBeHidden();
  });

  test("adds a card via the AI and reflects it in the board", async ({ page }) => {
    test.skip(
      !HAS_AI_KEY,
      "OPENROUTER_API_KEY not set; skipping live AI integration",
    );

    const stamp = Date.now();
    const cardTitle = `AI Test ${stamp}`;

    await page.getByRole("button", { name: "Chat" }).click();
    const sidebar = page.getByRole("complementary", { name: /ai chat/i });

    await sidebar
      .getByLabel("Message")
      .fill(`Add a card titled "${cardTitle}" to the Backlog column.`);
    await sidebar.getByRole("button", { name: /send/i }).click();

    await expect(sidebar.getByText(/board updated/i)).toBeVisible({
      timeout: 60_000,
    });

    const firstColumn = page.locator('[data-testid^="column-"]').first();
    await expect(firstColumn.getByText(cardTitle)).toBeVisible({
      timeout: 10_000,
    });

    // Cleanup so reruns don't accumulate cards in the shared dev DB
    await firstColumn
      .getByRole("button", { name: new RegExp(`delete ${cardTitle}`, "i") })
      .click();
    await expect(firstColumn.getByText(cardTitle)).not.toBeVisible();
  });
});
