import { test, expect } from '@playwright/test';

test.describe('Dark mode', () => {
  test('can toggle dark mode via navigation button', async ({ page }) => {
    // Serve the app in preview mode; baseURL is set to http://127.0.0.1:4173 in config
    await page.goto('http://127.01:4173/');
    // Initially dark mode class should not be present
    await expect(page.locator('html')).not.toHaveClass('dark');

    // Click the toggle button in Navigation (button with aria-label)
    await page.locator('button[aria-label="Toggle dark mode"]').click();

    // Now dark mode class should be added
    await expect(page.locator('html')).toHaveClass('dark');

    // Click again to toggle off
    await page.locator('button[aria-label="Toggle dark mode"]').click();
    await expect(page.locator('html')).not.toHaveClass('dark');
  });
});