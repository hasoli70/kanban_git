import { expect, test } from "@playwright/test";
import { loginAsTestUser } from "./helpers";

test("redirects unauthenticated visitor from / to /login", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/");
  await page.waitForURL("**/login");
  await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
});

test("logs in with valid credentials and shows the board", async ({ page }) => {
  await page.context().clearCookies();
  await loginAsTestUser(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
});

test("rejects invalid credentials", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel(/username/i).fill("user");
  await page.getByLabel(/password/i).fill("nope");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("alert")).toContainText(/invalid/i);
  expect(page.url()).toContain("/login");
});

test("logout returns to /login", async ({ page }) => {
  await page.context().clearCookies();
  await loginAsTestUser(page);
  await page.getByRole("button", { name: /^logout$/i }).click();
  await page.waitForURL("**/login");
});
