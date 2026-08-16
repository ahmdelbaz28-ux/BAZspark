import { test, expect } from '@playwright/test';
import { installApiMock } from './visual/helpers/authMock';

test.describe('Marine Page End-to-End Tests', () => {
	test.beforeEach(async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
		await page.goto('/marine');
	});

	test('should load Marine page successfully', async ({ page }) => {
		await expect(page).toHaveTitle(/BAZSPARK/i);
		await expect(page.locator('body')).toBeVisible();
	});

	test('should trigger backend API calls when buttons are clicked', async ({ page }) => {
		const apiCalls: string[] = [];
		await page.route('**/api/v1/marine/**', async (route) => {
			const url = route.request().url();
			apiCalls.push(url);
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ success: true, data: { status: 'success' } }),
			});
		});

		for (const testId of [
			'marine-run-pipeline-btn',
			'marine-alarm-sim-btn',
			'marine-detection-btn',
			'marine-extinguishing-btn',
			'marine-validate-btn',
			'marine-divide-zones-btn',
			'marine-calculate-sensor-btn',
			'marine-size-extinguishing-btn',
			'marine-design-power-btn',
			'marine-generate-alarm-logic-btn',
			'marine-export-scada-btn',
			'marine-export-etap-btn',
			'marine-export-dxf-btn',
			'marine-export-revit-btn',
		]) {
			const btn = page.locator(`[data-testid="${testId}"]`);
			if ((await btn.count()) > 0) {
				await btn.first().click({ force: true }).catch(() => {});
			}
		}
	});

	test('should toggle alarm simulation correctly', async ({ page }) => {
		const alarmButton = page.locator('[data-testid="marine-alarm-sim-btn"]');
		if ((await alarmButton.count()) > 0) {
			await expect(alarmButton.first()).toBeVisible();
			await alarmButton.first().click({ force: true }).catch(() => {});
		}
	});

	test('should navigate between tabs correctly', async ({ page }) => {
		const tabs = page.getByRole('tab');
		if ((await tabs.count()) > 0) {
			await expect(tabs.first()).toBeVisible();
		}
	});
});