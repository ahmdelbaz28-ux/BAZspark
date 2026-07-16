import { test, expect } from '@playwright/test';
import { installApiMock } from './helpers/authMock';

test.describe('Dark mode', () => {
  test('can toggle dark mode via navigation button', async ({ page }) => {
    // Pre-authenticate so the AppShell (with TopBar toggle button) renders
    await installApiMock(page, { preAuthenticated: true });

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Click the toggle button in TopBar (button with aria-label)
    await page.locator('button[aria-label="Toggle dark mode"]').click();

    // Now dark mode class should be added to html
    await expect(page.locator('html')).toHaveClass(/dark/);

    // Click again to toggle off
    await page.locator('button[aria-label="Toggle dark mode"]').click();
    await expect(page.locator('html')).not.toHaveClass(/dark/);
  });
});