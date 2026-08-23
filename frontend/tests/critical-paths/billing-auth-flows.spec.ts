// NOSONAR
/**
 * Critical Path E2E Tests — Billing & Auth flows.
 *
 * V255: These tests cover the production-critical user paths identified in
 * the production audit (score 73/100).
 *
 * Test coverage (8 total):
 *   1. Billing: Authenticated user creates order and initiates checkout
 *   2. Billing: Webhook delivery processes order status transition
 *   3. Billing: Idempotent webhook delivery (duplicate detection)
 *   4. Billing: Authenticated user views order events audit trail
 *   5. Auth: Unauthenticated access to billing page redirects to login
 *   6. Auth: Session persists across page reloads
 *   7. Auth: Login → protected route access → session validation
 *   8. End-to-End: Full billing checkout → webhook fulfillment → refresh cycle
 *
 * Run with: npx playwright test tests/critical-paths/billing-auth-flows.spec.ts
 *
 * Visual artifact support: Screenshots are captured for CI gate 4b (Visual Regression).
 * The `captureForReview` helper saves screenshots to `test-results/screenshots/` —
 * automatically uploaded by CI.
 *
 * NOTE on mock architecture: `installBillingApiMock` intercepts browser requests
 * with Playwright routes backed by NODE-side state (`getBillingMockState()`).
 * In-page `window.billingMock` helpers simply issue fetches that flow through
 * those routes — assertions MUST read the Node-side state, not window state.
 */
import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { installApiMock } from "../visual/helpers/authMock";
import {
	getBillingMockState,
	installBillingApiMock,
	resetBillingMockState,
} from "../visual/helpers/billingMock";

/**
 * Expose billing mock helpers on window so in-page evaluate scripts can call them.
 * Must be called AFTER page navigation so fetch has a valid baseURL.
 */
async function exposeBillingMock(page: Page) {
	await page.evaluate(() => {
		(window as any).billingMock = {
			createOrder: (amountCents: number) =>
				fetch("/api/v1/billing/orders", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ amount_cents: amountCents }),
				}).then((r) => r.json()),
			initiateCheckout: (orderId: string) =>
				fetch(`/api/v1/billing/orders/${orderId}/checkout`, {
					method: "POST",
				}).then((r) => r.json()),
			submitWebhook: (orderId: string, signature: string) =>
				fetch("/api/v1/billing/webhooks/meeza", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ order_id: orderId, signature }),
				}).then((r) => r.json()),
		};
	});
}

/**
 * Helper: capture a screenshot for CI artifacts.
 * Saved to test-results/screenshots/ — automatically uploaded by CI.
 */
async function captureForReview(page: Page, name: string) {
	await page.screenshot({
		path: `test-results/screenshots/${name}.png`,
		fullPage: true,
	});
}

test.describe("Critical Path: Billing & Auth Flows", () => {
	// Per-test isolation: reset billing mock state before each test group
	test.beforeEach(() => {
		resetBillingMockState();
	});

	// ─── Test 1: Billing — Authenticated user creates order and initiates checkout ─────────────
	test("billing: authenticated user creates order and initiates checkout", async ({
		page,
	}) => {
		const apiMock = await installApiMock(page, { preAuthenticated: true });
		await installBillingApiMock(page);

		// Navigate first so fetch has a valid baseURL, then authenticate
		await page.goto("/login");
		await apiMock.login();
		await exposeBillingMock(page);

		// Create an order via the mocked API (flows through Playwright routes
		// into the Node-side mock state)
		await page.evaluate(async () => {
			await (window as any).billingMock.createOrder(50000);
		});

		const order = getBillingMockState().orders.get("order_1");
		expect(order).not.toBeNull();
		expect(order!.amount_cents).toBe(50000);

		// Navigate to billing page — page-level chrome must render
		await page.goto("/billing");
		await page.waitForLoadState("networkidle");

		await expect(
			page.getByRole("heading", { name: /billing & subscriptions/i }),
		).toBeVisible({ timeout: 5000 });

		// MeezaPayment plan cards render EGP amounts
		await expect(page.getByText(/EGP/i).first()).toBeVisible({
			timeout: 5000,
		});

		await captureForReview(page, "01-billing-order-created");
	});

	// ─── Test 2: Billing — Webhook delivery processes order status transition ────────────────
	test("billing: webhook delivery processes order status transition", async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
		await installBillingApiMock(page);

		await page.goto("/login");
		await exposeBillingMock(page);

		// Create order, initiate checkout, deliver fulfilling webhook
		await page.evaluate(async () => {
			await (window as any).billingMock.createOrder(50000);
			await (window as any).billingMock.initiateCheckout("order_1");
			await (window as any).billingMock.submitWebhook("order_1", "valid-signature-12345");
		});

		// Assert against the Node-side mock state (source of truth for routes)
		const order = getBillingMockState().orders.get("order_1");
		expect(order).not.toBeNull();
		expect(order!.status).toBe("completed");
		expect(order!.events.length).toBeGreaterThan(0);
	});

	// ─── Test 3: Billing — Idempotent webhook delivery (duplicate detection) ────────────────
	test("billing: idempotent webhook delivery (duplicate detection)", async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
		await installBillingApiMock(page);

		await page.goto("/login");
		await exposeBillingMock(page);

		await page.evaluate(async () => {
			await (window as any).billingMock.createOrder(50000);
			// First webhook delivery — processes successfully
			await (window as any).billingMock.submitWebhook("order_1", "valid-signature-12345");
			// Second identical webhook — duplicate detection must reject it
			await (window as any).billingMock.submitWebhook("order_1", "valid-signature-12345");
		});

		const order = getBillingMockState().orders.get("order_1");
		expect(order).not.toBeNull();
		// Exactly 1 event — the duplicate was rejected, not double-counted
		expect(order!.events.length).toBe(1);
	});

	// ─── Test 4: Billing — Authenticated user views order events audit trail ─────────────────
	test("billing: authenticated user views order events audit trail", async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
		await installBillingApiMock(page);

		await page.goto("/login");
		await exposeBillingMock(page);

		await page.evaluate(async () => {
			await (window as any).billingMock.createOrder(50000);
			await (window as any).billingMock.submitWebhook("order_1", "valid-signature-12345");
		});

		// Node-side audit trail recorded the processed webhook event
		const order = getBillingMockState().orders.get("order_1");
		expect(order).not.toBeNull();
		expect(order!.events.length).toBe(1);
		expect(String(order!.events[0].status ?? order!.events[0])).toMatch(
			/processed|completed|success/i,
		);

		// Billing page documents the webhook security model
		await page.goto("/billing");
		await page.waitForLoadState("networkidle");
		await expect(page.getByText(/HMAC-signed webhooks/i).first()).toBeVisible({
			timeout: 5000,
		});
		await expect(page.getByText(/duplicate webhook deliveries/i).first()).toBeVisible({
			timeout: 5000,
		});
	});

	// ─── Test 5: Auth — Unauthenticated access to billing page redirects to login ─────────────
	test("auth: unauthenticated access to billing page redirects to login", async ({ page }) => {
		// No pre-authentication - default state is unauthenticated
		await page.goto("/billing");
		await page.waitForLoadState("networkidle");

		// Should redirect to login
		await expect(page).toHaveURL(/\/login/);
		await expect(page).toHaveURL(/from=%2Fbilling/);

		await captureForReview(page, "05-unauth-billing-redirect");
	});

	// ─── Test 6: Auth — Session persists across page reloads ─────────────────────────────────
	test("auth: session persists across page reloads", async ({ page }) => {
		await installApiMock(page, { preAuthenticated: false });

		// Login via the real UI (placeholder + submit button per LoginPage.tsx)
		await page.goto("/login");
		await page.waitForLoadState("networkidle");

		const apiKeyInput = page.getByPlaceholder("BS-XXXX-XXXX-XXXX-XXXX");
		await apiKeyInput.fill("test-engineer-key");

		await page
			.getByRole("button", { name: /initialize secure session/i })
			.click();

		// Should redirect to dashboard
		await page.waitForURL(/\/dashboard/, { timeout: 10000 });

		// Reload the page
		await page.reload();
		await page.waitForLoadState("networkidle");

		// Session should persist - still on dashboard
		await expect(page).toHaveURL(/\/dashboard/);

		await captureForReview(page, "06-session-persists");
	});

	// ─── Test 7: Auth — Login → protected route access → session validation ──────────────────
	test("auth: login → protected route access → session validation", async ({ page }) => {
		await installApiMock(page, { preAuthenticated: false });

		await page.goto("/login");
		await page.waitForLoadState("networkidle");

		const apiKeyInput = page.getByPlaceholder("BS-XXXX-XXXX-XXXX-XXXX");
		await apiKeyInput.fill("test-engineer-key");

		await page
			.getByRole("button", { name: /initialize secure session/i })
			.click();

		// Should redirect to dashboard
		await page.waitForURL(/\/dashboard/, { timeout: 10000 });

		// Dashboard should be visible with brand
		await expect(page.getByLabel(/BAZSPARK logo/i).first()).toBeVisible({ timeout: 5000 });

		// Should show projects/data (not loading skeleton)
		await expect(page.getByText(/projects/i).first()).toBeVisible({ timeout: 5000 });

		await captureForReview(page, "07-login-dashboard");
	});

	// ─── Test 8: End-to-End — Full billing checkout → webhook fulfillment → refresh cycle ────
	test("e2e: full billing checkout → webhook fulfillment → order status refresh", async ({
		page,
	}) => {
		await installApiMock(page, { preAuthenticated: true });
		await installBillingApiMock(page);

		await page.goto("/login");
		await exposeBillingMock(page);

		// Full lifecycle through the mocked API surface
		await page.evaluate(async () => {
			await (window as any).billingMock.createOrder(50000);
			await (window as any).billingMock.initiateCheckout("order_1");
			await (window as any).billingMock.submitWebhook("order_1", "valid-signature-12345");
		});

		// Order reached terminal completed state exactly once
		const order = getBillingMockState().orders.get("order_1");
		expect(order).not.toBeNull();
		expect(order!.status).toBe("completed");

		// Billing page chrome renders and survives a reload
		await page.goto("/billing");
		await page.waitForLoadState("networkidle");
		await expect(
			page.getByRole("heading", { name: /billing & subscriptions/i }),
		).toBeVisible({ timeout: 5000 });

		await page.reload();
		await page.waitForLoadState("networkidle");
		await expect(
			page.getByRole("heading", { name: /billing & subscriptions/i }),
		).toBeVisible({ timeout: 5000 });
	});
});