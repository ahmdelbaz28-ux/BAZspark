import { defineConfig } from "@playwright/test";

export default defineConfig({
  // Run ALL E2E tests (visual regression + integration tests).
  // Visual regression tests: ./tests/visual/
  // Integration tests: ./tests/*.spec.ts (e.g., simplified-button-tests.spec.ts, complete-button-backend-test.spec.ts)
  testDir: "./tests",
  timeout: 30000,
  retries: 1,
  // NOTE: global-auth-setup.ts is a test fixture extension, not a globalSetup file.
  // It's imported directly in test files that need auth mocking.
  use: {
    baseURL: process.env.PLAYWRIGHT_VISUAL_TESTS || process.env.CI ? "http://localhost:5173" : undefined,
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  },
  // Start webServer in CI or when visual tests are explicitly requested
  webServer: (process.env.PLAYWRIGHT_VISUAL_TESTS || process.env.CI)
    ? {
      command: "npx vite preview --port 5173",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    }
    : undefined,
});