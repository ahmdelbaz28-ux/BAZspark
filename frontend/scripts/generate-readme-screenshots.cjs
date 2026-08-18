const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const http = require("http");
const { spawn } = require("child_process");

const PORT = 4178;
const BASE_URL = `http://localhost:${PORT}`;
const OUTPUT_DIR = path.resolve(__dirname, "../../docs/assets/screenshots");

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// Sample rich data for realistic presentation
const sampleProject = {
  id: "proj-alpha-01",
  name: "BAZ Tower — Fire Protection & Life Safety",
  description: "NFPA 72 Compliant Commercial High-Rise Life Safety System",
  status: "Active",
  author: "Eng. Ahmed Elbaz",
  device_count: 48,
  connection_count: 36,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

const sampleDevices = [
  { id: "dev-01", name: "Photoelectric Smoke Detector SD-01", type: "FA_SMOKE", category: "FIRE_ALARM", x: 120, y: 150, z: 2.8, voltage: 24, current: 0.08, load: 1.92 },
  { id: "dev-02", name: "Multi-Criteria Sensor MC-02", type: "FA_SMOKE_HEAT", category: "FIRE_ALARM", x: 280, y: 150, z: 2.8, voltage: 24, current: 0.12, load: 2.88 },
  { id: "dev-03", name: "Addressable Horn Strobe HS-01", type: "FA_SOUND_STROBE", category: "FIRE_ALARM", x: 420, y: 220, z: 2.4, voltage: 24, current: 0.45, load: 10.8 },
  { id: "dev-04", name: "Manual Pull Station PS-01", type: "FA_PULL_STATION", category: "FIRE_ALARM", x: 80, y: 350, z: 1.2, voltage: 24, current: 0.02, load: 0.48 },
  { id: "dev-05", name: "Duct Smoke Detector DSD-01", type: "FA_DUCT_SMOKE", category: "FIRE_ALARM", x: 300, y: 380, z: 3.2, voltage: 24, current: 0.15, load: 3.6 },
  { id: "dev-06", name: "FACP Master Control Panel", type: "FA_PANEL", category: "CONTROL", x: 50, y: 50, z: 1.5, voltage: 24, current: 1.2, load: 28.8 }
];

async function startServer() {
  console.log(`Starting Vite preview server on port ${PORT}...`);
  const proc = spawn("npx", ["vite", "preview", "--port", String(PORT)], {
    cwd: path.resolve(__dirname, ".."),
    shell: true,
    stdio: "pipe",
  });

  proc.stdout.on("data", (d) => console.log(`[Vite]: ${d.toString().trim()}`));
  proc.stderr.on("data", (d) => console.log(`[Vite Err]: ${d.toString().trim()}`));

  // Wait for server to become responsive
  for (let i = 0; i < 30; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(BASE_URL, (res) => {
          if (res.statusCode === 200) resolve(true);
          else reject();
        });
        req.on("error", reject);
        req.setTimeout(1000, reject);
      });
      console.log("Vite preview server is ready!");
      return proc;
    } catch {
      await new Promise((r) => setTimeout(r, 500));
    }
  }
  throw new Error("Preview server failed to start");
}

async function setupPageMocks(page) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/api/v1/auth/me") || url.includes("/api/auth/me")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: {
            user_id: "usr_admin_01",
            role: "admin",
            username: "ahmed.elbaz",
            email: "engineering@bazspark.com",
            permissions: ["*"],
          },
        }),
      });
    }

    if (url.includes("/api/health") || url.includes("/api/v1/health")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: {
            status: "ok",
            database: "connected",
            engines: {
              nfpa72: "operational",
              nec_ch9: "operational",
              facp_agent: "operational",
              bim_twin: "operational",
            },
            uptime_human: "99.98%",
          },
        }),
      });
    }

    if (url.includes("/api/projects") || url.includes("/api/v1/projects")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: [sampleProject],
          pagination: { total: 1, page: 1, limit: 20 },
        }),
      });
    }

    if (url.includes("/api/devices") || url.includes("/api/v1/devices")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: sampleDevices,
        }),
      });
    }

    // Default fallback
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: method === "GET" ? [] : {},
      }),
    });
  });
}

const targets = [
  { route: "/dashboard", filename: "dashboard.png", desc: "System Dashboard" },
  { route: "/fire-alarm", filename: "fire-alarm-designer.png", desc: "Interactive Fire Alarm Designer" },
  { route: "/digital-twin", filename: "digital-twin.png", desc: "BIM Digital Twin Converter" },
  { route: "/engineering", filename: "engineering.png", desc: "Engineering Calculations Workspace" },
  { route: "/marine", filename: "marine.png", desc: "Marine SOLAS Fire Protection" },
  { route: "/facp", filename: "facp.png", desc: "Distributed Multi-Agent FACP" },
  { route: "/projects", filename: "projects.png", desc: "Project Management" },
  { route: "/reports", filename: "reports.png", desc: "Compliance & Report Center" },
  { route: "/connections", filename: "connections.png", desc: "Circuit Wiring & Topology" },
  { route: "/elements", filename: "elements.png", desc: "Device Inventory & Elements" },
  { route: "/settings", filename: "settings.png", desc: "System Settings & Configuration" },
  { route: "/compliance", filename: "compliance-center.png", desc: "Regulatory Compliance Center" },
];

async function run() {
  const serverProc = await startServer();

  let browser;
  try {
    try {
      browser = await chromium.launch({ channel: "msedge", headless: true });
    } catch {
      browser = await chromium.launch({ headless: true });
    }

    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
      colorScheme: "dark",
    });

    const page = await context.newPage();

    // Setup local storage seed and mocks
    await page.addInitScript(() => {
      window.localStorage.setItem("bazspark-visual-mode", "dark");
      window.localStorage.setItem("theme", "dark");
      window.localStorage.setItem(
        "nexus_project_state",
        JSON.stringify({
          currentProjectId: "proj-alpha-01",
          projects: [{ id: "proj-alpha-01", name: "BAZ Tower — Fire Protection" }],
        })
      );
    });

    await setupPageMocks(page);

    console.log("\nStarting screenshot captures...");
    for (const t of targets) {
      const url = `${BASE_URL}${t.route}`;
      console.log(`[Capture] ${t.desc} -> ${url}`);

      try {
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: 15000 });
        await page.waitForTimeout(2000);

        // Hide deprecation banner if open
        await page.evaluate(() => {
          const banner = document.querySelector('button[aria-label="Dismiss deprecation banner"]');
          if (banner) banner.click();
        });
        await page.waitForTimeout(500);

        const outPath = path.join(OUTPUT_DIR, t.filename);
        await page.screenshot({ path: outPath, fullPage: false });
        console.log(`  ✓ Saved: ${t.filename}`);
      } catch (err) {
        console.error(`  ✗ Error capturing ${t.filename}: ${err.message}`);
      }
    }

    console.log("\nAll screenshots generated successfully!");
  } finally {
    if (browser) await browser.close();
    serverProc.kill("SIGTERM");
  }
}

run().catch((e) => {
  console.error("Screenshot runner failed:", e);
  process.exit(1);
});
