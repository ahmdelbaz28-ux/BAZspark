/**
 * reduced-motion.spec.ts — WCAG prefers-reduced-motion compliance tests.
 *
 * Verifies that when the user sets their OS to "Reduce motion", all CSS
 * animations and transitions are effectively disabled via the universal
 * catch-all in index.css:
 *
 *   @media (prefers-reduced-motion: reduce) {
 *     *, *::before, *::after {
 *       animation-duration: 0.01ms !important;
 *       animation-iteration-count: 1 !important;
 *       animation-delay: 0s !important;
 *       transition-duration: 0.01ms !important;
 *       transition-delay: 0s !important;
 *     }
 *     body { cursor: auto !important; }
 *     .magnetic-cursor { display: none !important; }
 *   }
 *
 * Tests target login page elements with CSS transitions:
 * - .login-feature-item has transition: border-color 0.2s, transform 0.2s
 * - .login-submit-btn has transition: background-color 0.2s, transform 0.1s
 * - .login-input-control has transition: border-color 0.2s, box-shadow 0.2s
 * - .lang-toggle-btn has transition: border-color 0.2s, color 0.2s
 *
 * Note: Dashboard-only elements (.ask-ai-button) are NOT tested here
 * because they require a real backend or CI auth mock to log in.
 * The catch-all covers them identically via the universal selector.
 */

import { test, expect } from "@playwright/test";

test.describe("prefers-reduced-motion: reduce", () => {
	test.beforeEach(async ({ page }) => {
		await page.emulateMedia({ reducedMotion: "reduce" });
	});

	test("feature items: transitions are reduced to 0.01ms", async ({ page }) => {
		await page.goto("/login");
		await page.waitForSelector(".login-feature-item", { timeout: 10000 });

		const styles = await page.$$eval(".login-feature-item", (items) => {
			return items.slice(0, 3).map((el) => {
				const s = getComputedStyle(el);
				return {
					transitionDuration: parseFloat(s.transitionDuration),
					animationDuration: parseFloat(s.animationDuration),
				};
			});
		});

		for (const t of styles) {
			expect(t.transitionDuration).toBeLessThanOrEqual(0.02);
			expect(t.animationDuration).toBeLessThanOrEqual(0.02);
		}
	});

	test("submit button: transition is reduced to 0.01ms", async ({ page }) => {
		await page.goto("/login");
		await page.waitForSelector(".login-submit-btn", { timeout: 10000 });

		const s = await page.$eval(".login-submit-btn", (el) => {
			const style = getComputedStyle(el);
			return {
				transitionDuration: parseFloat(style.transitionDuration),
				animationDuration: parseFloat(style.animationDuration),
			};
		});

		expect(s.transitionDuration).toBeLessThanOrEqual(0.02);
		expect(s.animationDuration).toBeLessThanOrEqual(0.02);
	});

	test("form input: transition is reduced to 0.01ms", async ({ page }) => {
		await page.goto("/login");
		await page.waitForSelector(".login-input-control", { timeout: 10000 });

		const duration = await page.$eval(".login-input-control", (el) => {
			return parseFloat(getComputedStyle(el).transitionDuration);
		});

		expect(duration).toBeLessThanOrEqual(0.02);
	});

	test("language toggle: transition is reduced to 0.01ms", async ({ page }) => {
		await page.goto("/login");
		await page.waitForSelector(".lang-toggle-btn", { timeout: 10000 });

		const duration = await page.$eval(".lang-toggle-btn", (el) => {
			return parseFloat(getComputedStyle(el).transitionDuration);
		});

		expect(duration).toBeLessThanOrEqual(0.02);
	});

	test("magnetic cursor is not rendered", async ({ page }) => {
		await page.goto("/login");

		// With reduced motion, JS returns null (no rendering)
		expect(await page.$(".magnetic-cursor")).toBeNull();

		// cursor-active class should not be set on <html>
		const hasCursor = await page.evaluate(() =>
			document.documentElement.classList.contains("cursor-active"),
		);
		expect(hasCursor).toBe(false);
	});

	test("body shows native cursor", async ({ page }) => {
		await page.goto("/login");

		const cursor = await page.evaluate(() =>
			getComputedStyle(document.body).cursor,
		);

		expect(cursor).toBe("auto");
	});
});

test.describe("prefers-reduced-motion: no-preference (control)", () => {
	test("feature items: transitions run at their normal duration (0.2s)", async ({ page }) => {
		await page.emulateMedia({ reducedMotion: "no-preference" });
		await page.goto("/login");
		await page.waitForSelector(".login-feature-item", { timeout: 10000 });

		const debug = await page.$eval(".login-feature-item", (el) => {
			const style = getComputedStyle(el);
			return {
				transitionDuration: parseFloat(style.transitionDuration),
				transitionDurationRaw: style.getPropertyValue("transition-duration"),
				transitionShorthand: style.getPropertyValue("transition"),
				reducedMotionMatch: matchMedia("(prefers-reduced-motion: reduce)").matches,
			};
		});

		// Debug output for understanding why duration might be 0
		expect(debug.reducedMotionMatch).toBe(false);
		expect(debug.transitionDuration).toBeGreaterThanOrEqual(0.19);
	});

	test("submit button: transitions run at normal duration (0.2s)", async ({ page }) => {
		await page.emulateMedia({ reducedMotion: "no-preference" });
		await page.goto("/login");
		await page.waitForSelector(".login-submit-btn", { timeout: 10000 });

		const debug = await page.$eval(".login-submit-btn", (el) => {
			const style = getComputedStyle(el);
			return {
				transitionDuration: parseFloat(style.transitionDuration),
				transitionDurationRaw: style.getPropertyValue("transition-duration"),
				reducedMotionMatch: matchMedia("(prefers-reduced-motion: reduce)").matches,
			};
		});

		expect(debug.reducedMotionMatch).toBe(false);
		expect(debug.transitionDuration).toBeGreaterThanOrEqual(0.19);
	});

	test("form input: transition runs at normal duration (0.2s)", async ({ page }) => {
		await page.emulateMedia({ reducedMotion: "no-preference" });
		await page.goto("/login");
		await page.waitForSelector(".login-input-control", { timeout: 10000 });

		const debug = await page.$eval(".login-input-control", (el) => {
			const style = getComputedStyle(el);
			return {
				transitionDuration: parseFloat(style.transitionDuration),
				transitionDurationRaw: style.getPropertyValue("transition-duration"),
				reducedMotionMatch: matchMedia("(prefers-reduced-motion: reduce)").matches,
			};
		});

		expect(debug.reducedMotionMatch).toBe(false);
		expect(debug.transitionDuration).toBeGreaterThanOrEqual(0.19);
	});
});
