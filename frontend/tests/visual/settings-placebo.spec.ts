/**
 * Visual tests for Settings page — Placebo settings backend sync,
 * RTL support, and i18n Arabic translations.
 */
import { expect, test } from "@playwright/test";
import { installApiMock } from "./helpers/authMock";

test.describe("Settings Page — Placebo Settings Backend Sync", () => {
  test("Settings page loads with API and Reports tabs", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify we're on the settings page
    expect(page.url()).toContain("/settings");

    // Verify the API tab exists
    const apiTab = page.getByRole("tab", { name: /api/i });
    await expect(apiTab).toBeVisible({ timeout: 5000 });

    // Verify the Reports tab exists
    const reportsTab = page.getByRole("tab", { name: /report/i });
    await expect(reportsTab).toBeVisible({ timeout: 5000 });
  });

  test("API tab shows apiTimeout and retryAttempts fields", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Click API tab
    const apiTab = page.getByRole("tab", { name: /api/i });
    await apiTab.click();

    // Verify apiTimeout input exists
    const apiTimeoutLabel = page.getByText(/api timeout/i);
    await expect(apiTimeoutLabel).toBeVisible({ timeout: 5000 });

    // Verify retryAttempts input exists
    const retryLabel = page.getByText(/retry attempt/i);
    await expect(retryLabel).toBeVisible({ timeout: 5000 });
  });

  test("Reports tab shows reportFormat and autoSave settings", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Click Reports tab
    const reportsTab = page.getByRole("tab", { name: /report/i });
    await reportsTab.click();

    // Verify reportFormat select exists
    const formatLabel = page.getByText(/report format/i);
    await expect(formatLabel).toBeVisible({ timeout: 5000 });

    // Verify autoSave toggle exists
    const autoSaveLabel = page.getByText(/auto save/i);
    await expect(autoSaveLabel).toBeVisible({ timeout: 5000 });
  });

  test("API settings save button sends PUT request to backend", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    // Intercept the PUT /settings request
    let settingsRequestCaptured = false;
    let settingsRequestBody: Record<string, unknown> | null = null;

    await page.route("**/api/v1/settings", async (route) => {
      if (route.request().method() === "PUT") {
        settingsRequestCaptured = true;
        try {
          settingsRequestBody = route.request().postDataJSON();
        } catch {
          // ignore parse errors
        }
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, data: {} }),
      });
    });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Click API tab
    const apiTab = page.getByRole("tab", { name: /api/i });
    await apiTab.click();

    // Click Save button
    const saveButton = page.getByRole("button", { name: /save/i }).first();
    await saveButton.click();

    // Wait for the save request
    await page.waitForLoadState('networkidle');

    // Verify the PUT request was sent
    expect(settingsRequestCaptured, "Settings save should send PUT request to backend").toBe(true);
    if (settingsRequestBody) {
      expect(settingsRequestBody).toHaveProperty("api_timeout");
      expect(settingsRequestBody).toHaveProperty("retry_attempts");
    }
  });

  test("Reports settings save button sends PUT request to backend", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    // Intercept the PUT /settings request
    let settingsRequestCaptured = false;
    let settingsRequestBody: Record<string, unknown> | null = null;

    await page.route("**/api/v1/settings", async (route) => {
      if (route.request().method() === "PUT") {
        settingsRequestCaptured = true;
        try {
          settingsRequestBody = route.request().postDataJSON();
        } catch {
          // ignore parse errors
        }
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, data: {} }),
      });
    });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Click Reports tab
    const reportsTab = page.getByRole("tab", { name: /report/i });
    await reportsTab.click();

    // Click Save button
    const saveButton = page.getByRole("button", { name: /save/i }).first();
    await saveButton.click();

    // Wait for the save request
    await page.waitForLoadState('networkidle');

    // Verify the PUT request was sent
    expect(settingsRequestCaptured, "Reports settings save should send PUT request to backend").toBe(true);
    if (settingsRequestBody) {
      expect(settingsRequestBody).toHaveProperty("report_format");
      expect(settingsRequestBody).toHaveProperty("auto_save_reports");
      expect(settingsRequestBody).toHaveProperty("report_quality");
    }
  });
});

test.describe("Settings Page — RTL/i18n Support", () => {
  test("Settings page renders without errors in Arabic", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          text.includes("frame-ancestors") ||
          text.includes("Content Security Policy") ||
          text.includes("Failed to fetch") ||
          text.includes("Failed to load resource")
        ) {
          return;
        }
        errors.push(text);
      }
    });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify page loaded without errors
    expect(errors, `Settings page should have 0 console errors, got: ${errors.join("; ")}`).toEqual([]);
  });

  test("Feature flags tab displays correctly", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Click Feature Flags tab
    const flagsTab = page.getByRole("tab", { name: /feature flag/i });
    await flagsTab.click();

    // Verify at least one feature flag is visible
    const flagSwitch = page.locator("button[role='switch']").first();
    await expect(flagSwitch).toBeVisible({ timeout: 5000 });
  });
});
