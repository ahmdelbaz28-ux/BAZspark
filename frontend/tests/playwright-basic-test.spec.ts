// Test that Playwright works without a web server
import { test, expect } from '@playwright/test';

test('Playwright basic test', async ({ page }) => {
    // This test doesn't need a web server
    await page.setContent('<h1>Hello Playwright</h1>');
    const heading = page.locator('h1');
    await expect(heading).toHaveText('Hello Playwright');
});