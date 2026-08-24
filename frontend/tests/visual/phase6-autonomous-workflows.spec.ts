/**
 * Phase 6 Autonomous Engineering Workflows Visual / E2E Tests.
 */
import { expect, test } from "@playwright/test";
import { installApiMock } from "./helpers/authMock";

test.describe("Phase 6 — Autonomous Engineering Workflows", () => {
  test("Agent Control Center renders with AI-First Control Center layout", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/agent", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Context bar and header
    await expect(page.getByTestId("project-context-bar")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("FireAI Control Center").first()).toBeVisible({ timeout: 5000 });

    // Quick action cards
    const quickActions = page.locator("button").filter({ hasText: /Place Smoke Detectors|Voltage Drop/i });
    const count = await quickActions.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // Auto-approval toggle
    await expect(page.getByTestId("auto-approval-toggle-btn")).toBeVisible({ timeout: 5000 });
  });

  test("No unexpected console errors on Agent Control Center page", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/agent", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    const realErrors = consoleErrors.filter(
      (e) =>
        !e.includes("Failed to fetch") &&
        !e.includes("net::ERR_CONNECTION_REFUSED") &&
        !e.includes("ResizeObserver") &&
        !e.includes("401") &&
        !e.includes("503") &&
        !e.includes("Content Security Policy") &&
        !e.includes("Applying inline style violates") &&
        !e.includes("frame-ancestors") &&
        !e.includes("X-Frame-Options") &&
        !e.includes("Failed to load resource")
    );
    expect(realErrors).toHaveLength(0);
  });
});
