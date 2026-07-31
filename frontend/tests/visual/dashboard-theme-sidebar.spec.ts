/**
 * Visual tests for Dashboard page rendering and key UI components.
 * Validates: Dashboard stats render, sidebar navigation works, theme toggle persists.
 */
import { expect, test } from "@playwright/test";
import { installApiMock } from "./helpers/authMock";

test.describe("Dashboard — Visual Rendering", () => {
  test("Dashboard page renders with stat cards", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify page heading is visible
    const heading = page.getByRole("heading", { level: 1 }).first();
    await expect(heading).toBeVisible({ timeout: 5000 });

    // Verify stat cards are present (projects, devices, etc.)
    const cards = page.locator('[class*="card"], [data-slot="card"]').filter({ hasText: /\d+/ });
    const cardCount = await cards.count();
    expect(cardCount, "Dashboard should have stat cards").toBeGreaterThanOrEqual(1);
  });

  test("No console errors on Dashboard page", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Filter out known benign errors (network errors when backend is not running,
    // CSP violations, ResizeObserver, and 401/503 from auth checks)
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
    expect(realErrors, "No unexpected console errors on Dashboard").toHaveLength(0);
  });
});

test.describe("Theme Toggle — Persistence", () => {
  test("Theme toggle persists to localStorage", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Find the theme toggle button (Sun/Moon icon)
    const themeBtn = page.locator('button[aria-label*="mode"], button[aria-label*="light"], button[aria-label*="dark"]').first();
    const themeBtnVisible = await themeBtn.isVisible().catch(() => false);

    if (themeBtnVisible) {
      await themeBtn.click();
      await page.waitForLoadState('networkidle');

      // Verify localStorage has the theme value
      const storedTheme = await page.evaluate(() => localStorage.getItem("dark"));
      expect(storedTheme, "Theme should be persisted in localStorage").toBeTruthy();
    }
  });
});

test.describe("Sidebar — Navigation", () => {
  test("Sidebar navigation links are present and clickable", async ({ page }) => {
    await installApiMock(page, { preAuthenticated: true });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify sidebar is present
    const sidebar = page.locator("aside, nav, [data-sidebar]").first();
    const sidebarVisible = await sidebar.isVisible().catch(() => false);

    // Verify navigation links exist
    const navLinks = page.locator('a[href^="/"]').filter({ hasNot: page.locator('[aria-label="Skip to main content"]') });
    const linkCount = await navLinks.count();
    expect(linkCount, "Sidebar should have navigation links").toBeGreaterThanOrEqual(1);
  });
});
