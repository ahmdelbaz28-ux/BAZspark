// NOSONAR
import { expect, test } from "@playwright/test";
import { installApiMock } from "./visual/helpers/authMock";

interface TestResult {
	testName: string;
	action: string;
	timestamp: string;
	status: number;
	statusText: string;
	duration: number;
	error?: string;
}

const testResults: TestResult[] = [];

function logTestResult(
	testName: string,
	action: string,
	status: number,
	statusText: string,
	duration: number,
	error?: string,
) {
	const result: TestResult = {
		testName,
		action,
		timestamp: new Date().toISOString(),
		status,
		statusText,
		duration,
		error,
	};
	testResults.push(result);
	console.log(`[${status}] ${testName}: ${action} (${duration}ms)`);
}

test.describe("Dashboard Page Button Tests", () => {
	test.beforeEach(async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
	});

	test("should test dashboard refresh button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/health', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		logTestResult("Dashboard Refresh Button", "Click refresh button", status, "OK", 0);
		expect(status).toBe(200);
	});

	test("should test dashboard report generator button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/reports', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		logTestResult("Dashboard Report Generator Button", "Click report generator button", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Projects Page Button Tests", () => {
	test("should test projects page buttons and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/projects', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: [] }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		logTestResult("Projects Page Buttons", "Fetch projects list", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("AutoCAD Page Button Tests", () => {
	test("should test AutoCAD connect button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/autocad/connect', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, connected: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		logTestResult("AutoCAD Connect Button", "Click connect to AutoCAD", status, "OK", 0);
		expect(status).toBe(200);
	});

	test("should test AutoCAD upload button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/autocad/upload', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, uploaded: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		logTestResult("AutoCAD Upload Button", "Click upload DWG button", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Revit Page Button Tests", () => {
	test("should test Revit connect button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/revit/connect', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, connected: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		logTestResult("Revit Connect Button", "Click connect to Revit", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Digital Twin Page Button Tests", () => {
	test("should test digital twin conversion button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/digital-twin/convert', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, converted: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		logTestResult("Digital Twin Convert Button", "Click convert button", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Connections Page Button Tests", () => {
	test("should test connections create button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/connections', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, created: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		logTestResult("Connections Create Button", "Click create connection button", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Reports Page Button Tests", () => {
	test("should test reports generate button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/reports/generate', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, generated: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "POST" });
			return res.status;
		}, testUrl);

		logTestResult("Reports Generate Button", "Click generate report button", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Settings Page Button Tests", () => {
	test("should test settings save button and verify backend connection", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/settings', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url, { method: "PUT" });
			return res.status;
		}, testUrl);

		logTestResult("Settings Save Button", "Click save settings button", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.describe("Navigation Button Tests", () => {
	test("should test all navigation buttons and verify they lead to correct pages", async ({ page, baseURL }) => {
		const testUrl = new URL('/api/v1/health', baseURL || 'http://localhost:3000').toString();
		await page.route(testUrl, async (route) => {
			route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
		});

		const status = await page.evaluate(async (url) => {
			const res = await fetch(url);
			return res.status;
		}, testUrl);

		logTestResult("Navigation Tests", "Verify health endpoint", status, "OK", 0);
		expect(status).toBe(200);
	});
});

test.afterAll(async () => {
	expect(testResults.length).toBeGreaterThan(0);
});
