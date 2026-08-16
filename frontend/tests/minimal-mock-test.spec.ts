import { test, expect } from "@playwright/test";

test("minimal mock test", async ({ page, baseURL }) => {
  // Mock the API route first
  await page.route("**/api/test", route => {
    console.log("Mocked /api/test route hit");
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true }),
    });
  });

  // Trigger fetch directly via evaluate with absolute URL
  const testUrl = new URL('/api/test', baseURL || 'http://localhost:3000').toString();
  console.log(`Triggering fetch to: ${testUrl}`);
  const responsePromise = page.waitForResponse("**/api/test");
  await page.evaluate((url) => {
    fetch(url).catch(console.error);
  }, testUrl);

  const response = await responsePromise;
  console.log(`Response status: ${response.status()}`);
  expect(response.status()).toBe(200);
});