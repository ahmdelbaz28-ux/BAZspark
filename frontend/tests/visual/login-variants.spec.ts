/**
 * Visual tests for Login Variants (A, B, C)
 *
 * Tests that all three login variants render correctly:
 * - Form fields are visible
 * - Error alert renders properly
 * - Remember Me checkbox is present in all variants
 * - Language toggle works
 * - Arabic RTL layout renders correctly
 */

import { test, expect } from "@playwright/test";

// Mock auth to bypass login redirect
test.beforeEach(async ({ page }) => {
	await page.route("**/api/v1/auth/me", async (route) => {
		await route.fulfill({
			status: 401,
			contentType: "application/json",
			body: JSON.stringify({ success: false, error: "Not authenticated" }),
		});
	});
	await page.route("**/api/v1/health", async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({ success: true, data: { status: "ok", version: "1.0.0", database: "connected", uptime: 120 } }),
		});
	});
});

test.describe("Login Variant A — Engineering Terminal", () => {
	test("renders login form with all fields", async ({ page }) => {
		await page.goto("/login?variant=A");
		await page.waitForSelector("input[name='api_key']");

		// Check form fields are present
		const input = page.locator("input[name='api_key']");
		await expect(input).toBeVisible();

		// Check submit button
		const submitBtn = page.locator("button[type='submit']");
		await expect(submitBtn).toBeVisible();

		// Check language toggle
		const langToggle = page.locator("button[aria-label='Switch Language']");
		await expect(langToggle).toBeVisible();

		// Check remember checkbox
		const checkbox = page.locator("#remember");
		await expect(checkbox).toBeVisible();

		// Check hero title
		const heroTitle = page.locator(".login-hero-title");
		await expect(heroTitle).toBeVisible();
	});

	test("shows error alert on invalid submission", async ({ page }) => {
		await page.goto("/login?variant=A");
		await page.waitForSelector("input[name='api_key']");

		// Type and submit
		await page.fill("input[name='api_key']", "invalid-key");
		await page.route("**/api/v1/auth/login", async (route) => {
			await route.fulfill({
				status: 401,
				contentType: "application/json",
				body: JSON.stringify({ success: false, message: "Invalid Authorization key" }),
			});
		});
		await page.click("button[type='submit']");

		// Wait for error alert
		const alert = page.locator("[role='alert']");
		await expect(alert).toBeVisible({ timeout: 5000 });
	});
});

test.describe("Login Variant B — Minimal SaaS", () => {
	test("renders login form with remember checkbox", async ({ page }) => {
		await page.goto("/login?variant=B");
		await page.waitForSelector("input[name='api_key']");

		// Check form fields are present
		const input = page.locator("input[name='api_key']");
		await expect(input).toBeVisible();

		// Check remember checkbox (was missing before fix)
		const checkbox = page.locator("#remember");
		await expect(checkbox).toBeVisible();

		// Check submit button
		const submitBtn = page.locator("button[type='submit']");
		await expect(submitBtn).toBeVisible();
	});
});

test.describe("Login Variant C — Dark Portal", () => {
	test("renders login form with remember checkbox", async ({ page }) => {
		await page.goto("/login?variant=C");
		await page.waitForSelector("input[name='api_key']");

		// Check form fields are present
		const input = page.locator("input[name='api_key']");
		await expect(input).toBeVisible();

		// Check remember checkbox (was missing before fix)
		const checkbox = page.locator("#remember");
		await expect(checkbox).toBeVisible();

		// Check submit button
		const submitBtn = page.locator("button[type='submit']");
		await expect(submitBtn).toBeVisible();

		// Check particle canvas
		const canvas = page.locator("canvas");
		await expect(canvas).toBeVisible();
	});
});

test.describe("Login RTL — Arabic Layout", () => {
	test("renders Arabic layout correctly", async ({ page }) => {
		await page.goto("/login?variant=A");
		await page.waitForSelector("input[name='api_key']");

		// Click language toggle to switch to Arabic
		const langToggle = page.locator("button[aria-label='Switch Language']");
		await langToggle.click();

		// Check that dir="rtl" is set
		const root = page.locator(".login-screen-root");
		const dir = await root.getAttribute("dir");
		expect(dir).toBe("rtl");

		// Check that Arabic text is present
		const heroTitle = page.locator(".login-hero-title");
		const text = await heroTitle.textContent();
		expect(text).toMatch(/[\u0600-\u06FF]/); // Contains Arabic characters
	});
});
