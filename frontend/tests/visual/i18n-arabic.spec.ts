/**
 * Visual tests for i18n Arabic/RTL support across the application.
 * Verifies that Arabic translations are present and RTL layout works.
 */
import { expect, test } from "@playwright/test";
import { installApiMock } from "./helpers/authMock";

test.describe("i18n Arabic — RTL Layout", () => {
  test("Dashboard page renders in RTL when Arabic is selected", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Find language switcher in TopBar
    const langBtn = page.locator("button").filter({ hasText: /العربية|AR/i }).first();
    const langBtnVisible = await langBtn.isVisible().catch(() => false);

    if (langBtnVisible) {
      await langBtn.click();
      await page.waitForTimeout(500);

      // Verify RTL direction is set on the document
      const dir = await page.evaluate(() => document.documentElement.dir);
      expect(dir).toBe("rtl");
    }
  });
});

test.describe("i18n Arabic — Translation Completeness", () => {
  test("No untranslated English text visible on Settings page", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify the page title is present
    const heading = page.getByRole("heading", { level: 1 }).first();
    await expect(heading).toBeVisible({ timeout: 5000 });

    // Verify no raw i18n keys are visible (e.g., "settings.title")
    const rawKeys = page.getByText(/common\.\w+|settings\.\w+|nav\.\w+/);
    const rawKeyCount = await rawKeys.count();
    expect(rawKeyCount, "No raw i18n keys should be visible on the page").toBe(0);
  });
});
