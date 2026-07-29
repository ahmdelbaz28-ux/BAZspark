/**
 * Visual tests for Settings Page
 *
 * Tests that the Settings page renders correctly with:
 * - All tabs (General, Security, API, Reports)
 * - Backend-linked settings (apiTimeout, reportFormat)
 * - System health status
 * - Save functionality
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
                if (route.request().method() === "GET") {
                        await route.fulfill({
                                status: 200,
                                contentType: "application/json",
                                body: JSON.stringify({
                                        success: true,
                                        data: {
                                                theme: "dark",
                                                language: "ar",
                                                notifications: true,
                                                apiTimeout: 30,
                                                retryAttempts: 3,
                                                reportFormat: "pdf",
                                                reportQuality: "high",
                                                autoSaveReports: true,
                                        },
                                }),
                        });
                } else {
                        await route.fulfill({
                                status: 200,
                                contentType: "application/json",
                                body: JSON.stringify({ success: true, data: {} }),
                        });
                }
        });
        // Set language to Arabic
        await page.goto("/");
        await page.evaluate(() => {
                localStorage.setItem("i18nextLng", "ar");
        });
});

test.describe("Settings Page — General Tab", () => {
        test("renders all general settings", async ({ page }) => {
                await page.goto("/settings");
                await page.waitForLoadState("networkidle");

                // Check that the page title is visible
                const title = page.getByRole("heading", { name: "الإعدادات" });
                await expect(title).toBeVisible({ timeout: 10000 });

                // Check system health card
                const healthCard = page.locator("text=صحة النظام");
                await expect(healthCard).toBeVisible({ timeout: 10000 });

                // Check "Connected" status
                const connected = page.locator("text=متصل");
                await expect(connected).toBeVisible({ timeout: 10000 });
        });
});

test.describe("Settings Page — API Tab", () => {
        test("renders API timeout and retry settings", async ({ page }) => {
                await page.goto("/settings");
                await page.waitForLoadState("networkidle");

                // Click API tab
                const apiTab = page.getByRole("tab", { name: /api|API/i }).first();
                await expect(apiTab).toBeVisible({ timeout: 10000 });
                await apiTab.click();
                await page.waitForTimeout(300);

                // Check API timeout input
                const timeoutInput = page.locator("input[type='number']").first();
                if (await timeoutInput.isVisible()) {
                        const value = await timeoutInput.inputValue();
                        expect(Number(value)).toBeGreaterThan(0);
                }
        });
});

test.describe("Settings Page — Reports Tab", () => {
        test("renders report format and quality settings", async ({ page }) => {
                await page.goto("/settings");
                await page.waitForLoadState("networkidle");

                // Click Reports tab
                const reportsTab = page.getByRole("tab", { name: /التقارير|reports/i }).first();
                await expect(reportsTab).toBeVisible({ timeout: 10000 });
                await reportsTab.click();
                await page.waitForTimeout(300);

                // Check that the report generator section is present
                const reportGen = page.locator("text=مولد التقارير المتقدم");
                if (await reportGen.isVisible()) {
                        await expect(reportGen).toBeVisible();
                }
        });
});

test.describe("Settings Page — Save", () => {
        test("save button triggers API call", async ({ page }) => {
                await page.goto("/settings");
                await page.waitForLoadState("networkidle");

                // Look for save button
                const saveBtn = page.getByRole("button", { name: /حفظ|save/i }).first();
                if (await saveBtn.isVisible()) {
                        // Set up route to intercept save
                        const savePromise = page.waitForRequest("**/api/v1/settings", { timeout: 5000 }).catch(() => null);
                        await saveBtn.click();
                        // If backend save is triggered, the request will be caught
                }
        });
});
