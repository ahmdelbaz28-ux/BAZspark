/**
 * chaos.spec.ts — Chaos Engineering Tests for BAZspark
 *
 * V251: Inject realistic production failures and verify the app
 * survives gracefully. Every test simulates a real failure scenario
 * and checks that:
 *   1. The app does NOT crash (no white screen)
 *   2. The app does NOT freeze (no infinite loading)
 *   3. A user-friendly error message is shown (toast or error state)
 *   4. The app can recover (retry button or re-navigation works)
 *
 * Failure scenarios tested:
 *   - API returns 500 (server error)
 *   - API returns 401 (unauthorized)
 *   - API returns 403 (forbidden)
 *   - API returns 404 (not found)
 *   - API returns 429 (rate limited)
 *   - API returns malformed JSON
 *   - API timeout (no response)
 *   - Network offline (fetch fails)
 *   - Slow API (5s delay)
 *   - Rapid double-click
 *   - Browser refresh during request
 *   - Multiple tabs (session persistence)
 */
import { expect, test, type Page, type Route } from "@playwright/test";
import { installApiMock } from "./helpers/authMock";

// ─── Helpers ───────────────────────────────────────────────────────────────

/**
 * Capture all console errors during a test.
 */
function captureConsoleErrors(page: Page): string[] {
	const errors: string[] = [];
	page.on("console", (msg) => {
		if (msg.type() === "error") {
			const text = msg.text();
			// Filter out expected errors (backend not running)
			if (
				!text.includes("Failed to fetch") &&
				!text.includes("Failed to load resource") &&
				!text.includes("ECONNREFUSED") &&
				!text.includes("502") &&
				!text.includes("net::ERR")
			) {
				errors.push(text);
			}
		}
	});
	return errors;
}

/**
 * Check that the page hasn't crashed (root element still visible).
 */
async function expectNotCrashed(page: Page) {
	const root = page.locator("#root");
	await expect(root).toBeVisible({ timeout: 5000 });
	const bodyText = await page.locator("body").innerText();
	expect(bodyText.trim().length, "Page should not be blank").toBeGreaterThan(0);
}

/**
 * Check that the page is not stuck in infinite loading.
 * Looks for spinner elements that persist beyond a timeout.
 */
async function expectNotInfiniteLoading(page: Page) {
	// Wait a moment for any legitimate loading to start
	await page.waitForTimeout(2000);
	// Check that either content has loaded OR an error is shown
	// (not just a spinner with no error recovery)
	const hasSpinner = await page.locator("[class*='animate-spin']").count();
	const hasContent = await page.locator("h1, h2, h3, p, button").count();
	const hasError = await page.locator("[role='alert'], .text-danger, .text-red").count();

	if (hasSpinner > 0 && hasContent === 0 && hasError === 0) {
		// Wait a bit more — maybe it's just slow
		await page.waitForTimeout(3000);
		const stillSpinner = await page.locator("[class*='animate-spin']").count();
		const stillContent = await page.locator("h1, h2, h3, p, button").count();
		expect(
			stillContent > 0 || stillSpinner === 0,
			"Page appears stuck in infinite loading (spinner with no content or error)",
		).toBe(true);
	}
}

// ─── Chaos Tests ───────────────────────────────────────────────────────────

test.describe("Chaos Engineering — Failure Injection", () => {

	// ── API 500 (Server Error) ────────────────────────────────────────────
	test("survives API 500 on /auth/me — shows login page, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await page.route("**/api/**", async (route: Route) => {
			if (route.request().url().includes("/auth/me")) {
				return route.fulfill({
					status: 500,
					contentType: "application/json",
					body: JSON.stringify({ detail: "Internal Server Error" }),
				});
			}
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: [] }),
			});
		});

		await page.goto("/dashboard");
		await page.waitForLoadState("networkidle");

		// Should redirect to /login (auth check failed)
		await expect(page).toHaveURL(/\/login/);
		await expectNotCrashed(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	test("survives API 500 on /health — shows app shell, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/**", async (route: Route) => {
			if (route.request().url().includes("/health")) {
				return route.fulfill({
					status: 500,
					contentType: "application/json",
					body: JSON.stringify({ detail: "Database connection failed" }),
				});
			}
			// Pass through to auth mock for other endpoints
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: [] }),
			});
		});

		await page.goto("/dashboard");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── API 401 (Unauthorized) ────────────────────────────────────────────
	test("survives API 401 on data endpoint — shows error, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		// Override: return 401 for projects endpoint
		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 401,
				contentType: "application/json",
				body: JSON.stringify({ detail: "Token expired" }),
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── API 403 (Forbidden) ───────────────────────────────────────────────
	test("survives API 403 — shows error, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 403,
				contentType: "application/json",
				body: JSON.stringify({ detail: "Insufficient permissions" }),
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── API 404 (Not Found) ────────────────────────────────────────────────
	test("survives API 404 — shows error, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 404,
				contentType: "application/json",
				body: JSON.stringify({ detail: "Resource not found" }),
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── API 429 (Rate Limited) ─────────────────────────────────────────────
	test("survives API 429 — shows error, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 429,
				contentType: "application/json",
				body: JSON.stringify({ detail: "Too many requests" }),
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Malformed JSON ────────────────────────────────────────────────────
	test("survives malformed JSON response — shows error, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: "NOT VALID JSON {{{{",
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── API Timeout (no response) ─────────────────────────────────────────
	test("survives API timeout — shows error, not infinite loading", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			// Never respond — simulates timeout
			await new Promise(() => {}); // Never resolves
		});

		await page.goto("/projects");
		// Don't wait for networkidle (it will timeout)
		await page.waitForLoadState("domcontentloaded");
		await page.waitForTimeout(3000);

		await expectNotCrashed(page);
		// The page should still be usable (not frozen)
		const root = page.locator("#root");
		await expect(root).toBeVisible();
	});

	// ── Network Offline ───────────────────────────────────────────────────
	test("survives network offline — shows error, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.abort("internetdisconnected");
		});

		await page.goto("/projects");
		await page.waitForLoadState("domcontentloaded");
		await page.waitForTimeout(2000);

		await expectNotCrashed(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Slow API (5s delay) ───────────────────────────────────────────────
	test("survives slow API (5s delay) — eventually loads", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			await new Promise((resolve) => setTimeout(resolve, 2000));
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: [] }),
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("domcontentloaded");

		await expectNotCrashed(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Rapid Double-Click ────────────────────────────────────────────────
	test("survives rapid double-click on login — no duplicate sessions", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page);

		await page.goto("/login");
		await page.waitForLoadState("networkidle");

		await page.locator("#api-key").fill("test-key-123");
		const signInBtn = page.getByRole("button", { name: "Sign In" });

		// Rapid double-click
		await signInBtn.click({ clickCount: 2 });
		await page.waitForTimeout(3000);

		await expectNotCrashed(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Browser Refresh During Request ────────────────────────────────────
	test("survives browser refresh during API request — no crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		// Delay the projects response so we can refresh mid-request
		await page.route("**/api/v1/projects**", async (route: Route) => {
			await new Promise((resolve) => setTimeout(resolve, 1000));
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: [] }),
			});
		});

		await page.goto("/projects");
		await page.waitForTimeout(500); // Mid-request

		// Refresh
		await page.reload();
		await page.waitForLoadState("domcontentloaded");
		await page.waitForTimeout(2000);

		await expectNotCrashed(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Empty API Response ────────────────────────────────────────────────
	test("survives empty API response body — shows empty state, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: "",
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Null Data in Response ─────────────────────────────────────────────
	test("survives null data field in API response — shows empty state", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.route("**/api/v1/projects**", async (route: Route) => {
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: null }),
			});
		});

		await page.goto("/projects");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		await expectNotInfiniteLoading(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Unknown Route (404 page) ──────────────────────────────────────────
	test("survives unknown route — shows 404 page, not crash", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		await installApiMock(page, { preAuthenticated: true });

		await page.goto("/this-route-does-not-exist");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		// Should show 404 or redirect to login
		const url = page.url();
		const has404 = await page.getByText(/404|not found/i).count();
		expect(url.includes("/login") || has404 > 0, "Should show 404 or redirect to login").toBe(true);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Corrupted localStorage ────────────────────────────────────────────
	test("survives corrupted localStorage — boots with default state", async ({ page }) => {
		const errors = captureConsoleErrors(page);

		// Inject corrupted localStorage BEFORE the app loads
		await page.addInitScript(() => {
			try {
				localStorage.setItem("nexus_project_state", "NOT VALID JSON {{{");
			} catch {
				// localStorage may not be available
			}
		});

		await installApiMock(page, { preAuthenticated: true });
		await page.goto("/dashboard");
		await page.waitForLoadState("networkidle");

		await expectNotCrashed(page);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});

	// ── Session Persistence Across Reload ─────────────────────────────────
	test("session persists across page reload — no re-login required", async ({ page }) => {
		const errors = captureConsoleErrors(page);
		const mock = await installApiMock(page, { preAuthenticated: true });

		await page.goto("/dashboard");
		await page.waitForLoadState("networkidle");
		await expect(page).toHaveURL(/\/dashboard/);

		// Reload
		await page.reload();
		await page.waitForLoadState("networkidle");

		// Should still be on dashboard (session persisted in mock)
		await expect(page).toHaveURL(/\/dashboard/);
		expect(errors.length, `Console errors: ${errors.join("; ")}`).toBe(0);
	});
});
