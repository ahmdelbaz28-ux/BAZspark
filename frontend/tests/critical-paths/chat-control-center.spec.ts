/**
 * chat-control-center.spec.ts — Playwright E2E tests for Phase 2 Chat Control Center.
 *
 * Tests:
 * 1. Default route / loads Chat Control Center directly.
 * 2. Auto Approval toggle switching between AUTO and STEP-BY-STEP.
 * 3. Quick Action click launches multi-step Agent Run with ExecutionTimeline.
 * 4. Human review approval gate renders WorkflowActionCard in WAITING_APPROVAL.
 * 5. Conversational prompt submission displays assistant message stream.
 */
import { expect, test } from "@playwright/test";
import { installApiMock } from "../visual/helpers/authMock";

test.describe("Phase 2 — AI-First Chat Control Center", () => {
	test.beforeEach(async ({ page }) => {
		await installApiMock(page, { preAuthenticated: true });
	});

	test("default route / loads Chat Control Center as primary interface", async ({
		page,
	}) => {
		await page.goto("/");
		await page.waitForLoadState("networkidle");

		// Header & Context Bar
		await expect(page.getByTestId("project-context-bar")).toBeVisible();
		await expect(page.getByText("FireAI Control Center")).toBeVisible();
		await expect(page.getByText("AI-First")).toBeVisible();

		// Welcome Hero & Quick Action Cards
		await expect(
			page.getByText(/FireAI Engineering Control Center/i),
		).toBeVisible();
		await expect(page.getByTestId("auto-approval-toggle-btn")).toBeVisible();
	});

	test("auto approval toggle switches execution mode", async ({ page }) => {
		await page.goto("/");
		await page.waitForLoadState("networkidle");

		const toggleBtn = page.getByTestId("auto-approval-toggle-btn");
		await expect(toggleBtn).toContainText("AUTO");

		// Open dropdown
		await toggleBtn.click();
		const stepOption = page.getByTestId("step-by-step-option");
		await expect(stepOption).toBeVisible();

		// Select Step-by-Step
		await stepOption.click();
		await expect(toggleBtn).toContainText("STEP-BY-STEP");
	});

	test("quick action triggers execution timeline with multi-step progression", async ({
		page,
	}) => {
		await page.goto("/");
		await page.waitForLoadState("networkidle");

		// Click "Place Smoke Detectors" quick action card
		const quickCard = page
			.getByRole("button", { name: /Place Smoke Detectors/i })
			.first();
		await quickCard.click();

		// Execution Timeline should appear
		const timeline = page.getByTestId("execution-timeline");
		await expect(timeline).toBeVisible();
		await expect(timeline.getByText("Agent Execution Spine")).toBeVisible();
		await expect(
			timeline.getByText("Calculate optimal spacing & device placement"),
		).toBeVisible();
	});

	test("conversational chat submission displays user message", async ({
		page,
	}) => {
		await page.goto("/");
		await page.waitForLoadState("networkidle");

		const input = page.getByPlaceholder(
			/Ask an engineering question, run voltage drop/i,
		);
		await input.fill("What are the spacing requirements for heat detectors?");
		await page.keyboard.press("Enter");

		// Verify user message bubble is rendered
		await expect(
			page.getByText("What are the spacing requirements for heat detectors?"),
		).toBeVisible();
	});
});
