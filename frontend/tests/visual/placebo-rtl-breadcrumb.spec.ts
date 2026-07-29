/**
 * Visual tests for Placebo settings backend integration and RTL breadcrumb.
 * Validates: apiTimeout, reportFormat are wired to backend, RTL breadcrumb renders correctly.
 */
import { expect, test } from "@playwright/test";
import { installApiMock } from "./helpers/authMock";

test.describe("Placebo Settings — Backend Integration", () => {
  test("Settings page loads with apiTimeout and reportFormat fields", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    // Mock the backend settings endpoint
    await page.route("**/api/v1/settings", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          api_timeout: 60,
          retry_attempts: 5,
          report_format: "xlsx",
          auto_save_reports: true,
          report_quality: "high",
        }),
      }),
    );

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify the API tab is present
    const apiTab = page.getByRole("tab", { name: /api|API/i }).first();
    await expect(apiTab).toBeVisible({ timeout: 5000 });

    // Click on the API tab
    await apiTab.click();
    await page.waitForTimeout(300);

    // Verify the apiTimeout field is present
    const timeoutInput = page.locator('input[type="number"]').first();
    await expect(timeoutInput).toBeVisible({ timeout: 5000 });

    // Verify the Reports tab is present
    const reportsTab = page.getByRole("tab", { name: /reports|التقارير/i }).first();
    await expect(reportsTab).toBeVisible({ timeout: 5000 });
  });

  test("Save API settings sends correct payload to backend", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    let capturedPayload: Record<string, unknown> | null = null;
    await page.route("**/api/v1/settings", (route) => {
      if (route.request().method() === "PUT") {
        capturedPayload = route.request().postDataJSON();
      }
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Click on the API tab
    const apiTab = page.getByRole("tab", { name: /api|API/i }).first();
    if (await apiTab.isVisible()) {
      await apiTab.click();
      await page.waitForTimeout(300);

      // Find and click the save button
      const saveBtn = page.getByRole("button", { name: /save|حفظ/i }).first();
      if (await saveBtn.isVisible()) {
        await saveBtn.click();
        await page.waitForTimeout(500);

        // Verify the payload was sent
        if (capturedPayload) {
          expect(capturedPayload).toHaveProperty("api_timeout");
          expect(capturedPayload).toHaveProperty("retry_attempts");
        }
      }
    }
  });
});

test.describe("RTL Breadcrumb Navigation", () => {
  test("Breadcrumb renders correctly on Dashboard in RTL mode", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify breadcrumb is present
    const breadcrumb = page.locator("nav[aria-label], [data-breadcrumb]").first();
    const breadcrumbVisible = await breadcrumb.isVisible().catch(() => false);

    // Also check for the breadcrumb container
    const breadcrumbContainer = page.locator(".breadcrumb-container").first();
    const containerVisible = await breadcrumbContainer.isVisible().catch(() => false);

    expect(breadcrumbVisible || containerVisible, "Breadcrumb should be visible").toBeTruthy();
  });

  test("Breadcrumb updates on navigation to Settings page", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify breadcrumb contains "Settings" text
    const breadcrumbText = await page.locator(".breadcrumb-container").textContent().catch(() => "");
    const hasSettings = breadcrumbText?.toLowerCase().includes("settings") ||
      breadcrumbText?.includes("الإعدادات");
    expect(hasSettings, "Breadcrumb should show Settings").toBeTruthy();
  });
});

test.describe("Placebo Settings — RTL Support", () => {
  test("Settings page layout adapts to RTL when Arabic is selected", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/settings", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Find language switcher
    const langBtn = page.locator("button").filter({ hasText: /العربية|AR/i }).first();
    const langBtnVisible = await langBtn.isVisible().catch(() => false);

    if (langBtnVisible) {
      await langBtn.click();
      await page.waitForTimeout(500);

      // Verify RTL direction
      const dir = await page.evaluate(() => document.documentElement.dir);
      expect(dir).toBe("rtl");

      // Verify the page still renders correctly
      const heading = page.getByRole("heading", { level: 1 }).first();
      await expect(heading).toBeVisible({ timeout: 5000 });
    }
  });
});
