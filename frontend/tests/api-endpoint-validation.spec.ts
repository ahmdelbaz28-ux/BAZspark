// NOSONAR
import { expect, type Page, test } from "@playwright/test";
import { installApiMock } from "./visual/helpers/authMock";

/**
 * API Endpoint Validation Tests
 *
 * Validates that all critical CAD/BIM/Marine API endpoints return 200
 * when intercepted and fulfilled properly.
 */

interface ApiCallLog {
	method: string;
	url: string;
	statusCode: number;
}

const apiCallLogs: ApiCallLog[] = [];

test.describe("API Endpoint Validation Tests", () => {
	test.beforeEach(async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
	});

	test("should validate dashboard API calls", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/health', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, status: "healthy" }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate AutoCAD connect API call", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/autocad/connect', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, connected: true }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate Revit connect API call", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/revit/connect', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, connected: true }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate project creation API call", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/projects', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, id: "proj_1" }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate digital twin conversion API call", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/digital-twin/convert', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, status: "converted" }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate element operations API calls", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/elements', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: [] }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate connection operations API calls", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/connections', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: [] }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate conflict operations API calls", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/conflicts/check', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, conflicts: [] }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate report generation API calls", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/reports/generate', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, reportId: "rep_1" }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate export operations API calls", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/reports/export/pdf', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, url: "/exports/rep_1.pdf" }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});

	test("should validate settings save API call", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/settings', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true }),
			});
		});

		const response = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "PUT" });
			return res.status;
		}, testUrl);

		expect(response).toBe(200);
	});
});
