/**
 * agentWorkflowApi.test.ts — Unit tests for agentWorkflowApi (Phase 6).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { agentWorkflowApi } from "../agentWorkflowApi";

vi.mock("../csrf", () => ({
	getCachedCsrfToken: () => "mock-csrf-token",
	getCsrfToken: async () => "mock-csrf-token",
	invalidateCsrfToken: () => {},
	CSRF_HEADER_NAME: "X-CSRF-Token",
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("agentWorkflowApi", () => {
	beforeEach(() => {
		mockFetch.mockReset();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	it("plans a workflow using planWorkflow", async () => {
		const fakePlan = {
			plan_id: "plan-123",
			project_id: "proj-1",
			expected_revision: 1,
			intent_summary: "Test workflow",
			steps: [],
			dag: { nodes: [] },
			requires_human_approval: false,
			overall_policy_decision: "APPROVED",
			projected_state: {},
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakePlan }),
			text: async () => JSON.stringify({ success: true, data: fakePlan }),
		});

		const plan = await agentWorkflowApi.planWorkflow({
			prompt: "Place smoke detectors",
			projectId: "proj-1",
		});

		expect(mockFetch).toHaveBeenCalledWith(
			expect.stringContaining("/workflow/runs/plan"),
			expect.objectContaining({ method: "POST" }),
		);
		expect(plan.plan_id).toBe("plan-123");
	});

	it("starts a planned workflow using startPlannedWorkflow", async () => {
		const fakeRun = {
			runId: "run-123",
			projectId: "proj-1",
			status: "RUNNING",
			approvalMode: "AUTO",
			currentStep: "step-1",
			completedSteps: [],
			failedSteps: [],
			pendingApprovalId: null,
			recoveryState: {},
			auditReference: "audit-1",
			version: 1,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakeRun }),
			text: async () => JSON.stringify({ success: true, data: fakeRun }),
		});

		const result = await agentWorkflowApi.startPlannedWorkflow({
			prompt: "Start workflow",
			projectId: "proj-1",
		});

		expect(mockFetch).toHaveBeenCalledWith(
			expect.stringContaining("/workflow/runs/start-plan"),
			expect.objectContaining({ method: "POST" }),
		);
		expect((result as unknown as Record<string, unknown>).run_id ?? result.runId).toBe("run-123");
	});

	it("fetches run status using getRunStatus", async () => {
		const fakeRun = {
			runId: "run-456",
			projectId: "proj-1",
			status: "COMPLETED",
			approvalMode: "AUTO",
			currentStep: null,
			completedSteps: ["step-1"],
			failedSteps: [],
			pendingApprovalId: null,
			recoveryState: {},
			auditReference: "audit-1",
			version: 2,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakeRun }),
			text: async () => JSON.stringify({ success: true, data: fakeRun }),
		});

		const status = await agentWorkflowApi.getRunStatus("run-456");
		expect(mockFetch).toHaveBeenCalledWith(
			expect.stringContaining("/workflow/runs/run-456/status"),
			expect.objectContaining({ method: "GET" }),
		);
		expect(status.status).toBe("COMPLETED");
	});

	it("resumes an agent run using resumeRun", async () => {
		const fakeRun = {
			runId: "run-456",
			projectId: "proj-1",
			status: "RUNNING",
			approvalMode: "AUTO",
			currentStep: "step-2",
			completedSteps: ["step-1"],
			failedSteps: [],
			pendingApprovalId: null,
			recoveryState: {},
			auditReference: "audit-1",
			version: 3,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakeRun }),
			text: async () => JSON.stringify({ success: true, data: fakeRun }),
		});

		const result = await agentWorkflowApi.resumeRun("run-456");
		expect(result.status).toBe("RUNNING");
	});

	it("cancels an agent run using cancelRun", async () => {
		const fakeRun = {
			runId: "run-456",
			projectId: "proj-1",
			status: "CANCELLED",
			approvalMode: "AUTO",
			currentStep: null,
			completedSteps: ["step-1"],
			failedSteps: [],
			pendingApprovalId: null,
			recoveryState: {},
			auditReference: "audit-1",
			version: 4,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakeRun }),
			text: async () => JSON.stringify({ success: true, data: fakeRun }),
		});

		const result = await agentWorkflowApi.cancelRun("run-456");
		expect(result.status).toBe("CANCELLED");
	});

	it("retries an agent run using retryRun", async () => {
		const fakeRun = {
			runId: "run-456",
			projectId: "proj-1",
			status: "RUNNING",
			approvalMode: "AUTO",
			currentStep: "step-2",
			completedSteps: ["step-1"],
			failedSteps: [],
			pendingApprovalId: null,
			recoveryState: {},
			auditReference: "audit-1",
			version: 5,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakeRun }),
			text: async () => JSON.stringify({ success: true, data: fakeRun }),
		});

		const result = await agentWorkflowApi.retryRun("run-456");
		expect(result.status).toBe("RUNNING");
	});

	it("submits approval decision using decideApproval", async () => {
		const fakeRun = {
			runId: "run-456",
			projectId: "proj-1",
			status: "RUNNING",
			approvalMode: "STEP_BY_STEP",
			currentStep: "step-2",
			completedSteps: ["step-1"],
			failedSteps: [],
			pendingApprovalId: null,
			recoveryState: {},
			auditReference: "audit-1",
			version: 6,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, data: fakeRun }),
			text: async () => JSON.stringify({ success: true, data: fakeRun }),
		});

		const result = await agentWorkflowApi.decideApproval("run-456", "appr-1", "APPROVED", "Approved by engineer");
		expect(result.status).toBe("RUNNING");
	});
});
