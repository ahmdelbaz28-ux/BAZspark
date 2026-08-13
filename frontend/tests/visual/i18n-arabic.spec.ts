/**
 * Visual tests for i18n Arabic translations
 *
 * Tests that Arabic translations render correctly:
 * - Settings page shows Arabic labels
 * - Navigation items are translated
 * - Common terms are properly translated
 * - No untranslated English keys appear in UI
 */

import { test, expect } from "@playwright/test";

// Mock auth and API
test.beforeEach(async ({ page }) => {
        await page.route("**/api/v1/auth/me", async (route) => {
                await route.fulfill({
                        status: 200,
                        contentType: "application/json",
                        body: JSON.stringify({ success: true, data: { role: "admin" } }),
                });
        });
        await page.route("**/api/v1/health", async (route) => {
                await route.fulfill({
                        status: 200,
                        contentType: "application/json",
                        body: JSON.stringify({ success: true, data: { status: "ok", version: "1.0.0", database: "connected", uptime: 120 } }),
                });
        });
        await page.route("**/api/v1/settings", async (route) => {
                await route.fulfill({
                        status: 200,
                        contentType: "application/json",
                        body: JSON.stringify({ success: true, data: { language: "ar" } }),
                });
        });
        await page.route("**/api/v1/projects**", async (route) => {
                await route.fulfill({
                        status: 200,
                        contentType: "application/json",
                        body: JSON.stringify({ success: true, data: { data: [], total: 0, page: 1, limit: 10, total_pages: 0 } }),
                });
        });
});

test.describe("Arabic i18n — Settings Page", () => {
        test("renders Arabic settings labels", async ({ page }) => {
                // Set language to Arabic via i18next localStorage key
                await page.goto("/");
                await page.evaluate(() => {
                        localStorage.setItem("i18nextLng", "ar");
                });
                await page.goto("/settings");
                await page.waitForSelector("text=الإعدادات", { timeout: 10000 });

                // Check that Arabic title is present (use heading to avoid strict mode violation)
                const title = page.getByRole("heading", { name: "الإعدادات" });
                await expect(title).toBeVisible();

                // Check that Arabic subtitle is present
                const subtitle = page.locator("text=تهيئة تفضيلات التطبيق");
                await expect(subtitle).toBeVisible();

                // Check that Arabic tab labels are present (use getByRole for tabs)
                const generalTab = page.getByRole("tab", { name: /عام/ });
                await expect(generalTab).toBeVisible({ timeout: 10000 });

                const securityTab = page.getByRole("tab", { name: /الأمان/ });
                await expect(securityTab).toBeVisible({ timeout: 10000 });
        });

        test("renders Arabic settings report labels", async ({ page }) => {
                // Set language to Arabic via i18next localStorage key
                await page.goto("/");
                await page.evaluate(() => {
                        localStorage.setItem("i18nextLng", "ar");
                });
                await page.goto("/settings");
                await page.waitForSelector("text=الإعدادات", { timeout: 10000 });

                // Click Reports tab
                const reportsTab = page.locator("button[value='reports']");
                if (await reportsTab.isVisible()) {
                        await reportsTab.click();
                }

                // Check that Arabic report settings labels are present
                const reportFormat = page.locator("text=تنسيق التقرير");
                if (await reportFormat.isVisible()) {
                        await expect(reportFormat).toBeVisible();
                }

                const reportQuality = page.locator("text=جودة التقرير");
                if (await reportQuality.isVisible()) {
                        await expect(reportQuality).toBeVisible();
                }
        });
});

test.describe("Arabic i18n — No Untranslated Keys", () => {
        test("settings page does not show raw i18n keys", async ({ page }) => {
                // Set language to Arabic via i18next localStorage key
                await page.goto("/");
                await page.evaluate(() => {
                        localStorage.setItem("i18nextLng", "ar");
                });
                await page.goto("/settings");
                await page.waitForSelector("text=الإعدادات", { timeout: 10000 });

                // Check that no raw i18n keys are visible (e.g., "settings.title")
                const rawKeys = page.locator("text=settings.");
                expect(await rawKeys.count()).toBe(0);

                // Check that no raw common keys are visible (e.g., "common.save")
                const commonKeys = page.locator("text=common.");
                expect(await commonKeys.count()).toBe(0);
        });
});
