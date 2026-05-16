import type { Page } from "@playwright/test";

export async function loginAsTestUser(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/username/i).fill("user");
  await page.getByLabel(/password/i).fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("**/");
}
