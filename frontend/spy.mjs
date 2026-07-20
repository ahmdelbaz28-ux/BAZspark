import { chromium } from "playwright";
import { exec } from "child_process";
import http from "http";

// Start the preview server
// S4036: NOSONAR — this is a test/dev script; npm location is controlled by the dev environment
const serverProcess = exec("npx --yes vite preview --port 4173 --strictPort --host 127.0.0.1", { cwd: "." });  // NOSONAR - javascript:S4036
serverProcess.stdout.on("data", (data) => console.log(`[Server] ${data.trim()}`));
serverProcess.stderr.on("data", (data) => console.error(`[Server Error] ${data.trim()}`));

// Helper to poll the server until it responds
async function waitForServer(url, timeoutMs = 10000) {
	const startTime = Date.now();
	while (Date.now() - startTime < timeoutMs) {
		try {
			await new Promise((resolve, reject) => {
				const req = http.get(url, (res) => {
					if (res.statusCode === 200) resolve();
					else reject();
				});
				req.on("error", reject);
				req.end();
			});
			console.log("Server is up and running!");
			return;
		} catch {
			await new Promise(r => setTimeout(r, 200));
		}
	}
	throw new Error("Server failed to start in time");
}

try {
	console.log("Waiting for server...");
	await waitForServer("http://127.0.0.1:4173");

	console.log("Launching browser...");
	const browser = await chromium.launch({ headless: true });
	const context = await browser.newContext();
	const page = await context.newPage();

	// Log console messages
	page.on("console", msg => {
		console.log(`[Browser Console ${msg.type()}] ${msg.text()}`);
	});

	// Log page errors
	page.on("pageerror", err => {
		console.error(`[Browser Page Error] ${err.stack || err.message}`);
	});

	// Log network requests
	page.on("request", req => {
		console.log(`[Request] ${req.method()} ${req.url()}`);
	});

	page.on("requestfailed", req => {
		console.error(`[Request FAILED] ${req.method()} ${req.url()} - ${req.failure()?.errorText}`);
	});

	page.on("response", res => {
		console.log(`[Response] ${res.status()} ${res.url()}`);
	});

	// Install the API mock (simplified)
	let isAuthenticated = false;
	await page.route("**/api/**", async (route) => {
		const url = route.request().url();
		const method = route.request().method();
		console.log(`[Mock Intercept] ${method} ${url}`);

		if (url.includes("/auth/me")) {
			if (isAuthenticated) {
				return route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({ success: true, data: { role: "engineer" } })
				});
			} else {
				return route.fulfill({
					status: 401,
					contentType: "application/json",
					body: JSON.stringify({ success: false, detail: "Not authenticated" })
				});
			}
		}

		if (url.includes("/auth/login") && method === "POST") {
			isAuthenticated = true;
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				headers: { "Set-Cookie": "mock_session=engineer; Path=/; HttpOnly" },
				body: JSON.stringify({ success: true, data: { role: "engineer" } })
			});
		}

		if (url.includes("/csrf-token")) {
			return route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ success: true, data: { csrf_token: "mock-csrf-token" } })
			});
		}

		return route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({ success: true, data: [] })
		});
	});

	console.log("Navigating to /login...");
	await page.goto("http://127.0.0.1:4173/login");

	console.log("Waiting 2 seconds...");
	await new Promise(resolve => setTimeout(resolve, 2000));

	console.log("Filling API key...");
	await page.locator("#api-key").fill("test-engineer-key");

	console.log("Clicking Sign In...");
	await page.getByRole("button", { name: "Sign In" }).click();

	console.log("Waiting 5 seconds for navigation...");
	await new Promise(resolve => setTimeout(resolve, 5000));

	console.log(`Final URL: ${page.url()}`);
	await browser.close();
} catch (e) {
	console.error(e);
} finally {
	console.log("Terminating server...");
	serverProcess.kill("SIGKILL");
}
