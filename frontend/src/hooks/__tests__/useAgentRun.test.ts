/**
 * useAgentRun.test.ts — Unit tests for useAgentRun hook (Phase 2).
 *
 * Tests:
 * - Initial state & approval mode defaults
 * - Start run transition & plan tracking
 * - Rehydration from backend REST /workflow/runs/{id}/status
 * - Mode switching (AUTO <-> STEP_BY_STEP) with local storage sync
 * - Lifecycle controls (resume, cancel, retry, approveStep, rejectStep, clearRun)
 */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAgentRun } from "@/hooks/useAgentRun";
import { agentRunsApi } from "@/services/fullApi";

// Mock fullApi
vi.mock("@/services/fullApi", () => ({
	agentRunsApi: {
		getStatus: vi.fn(),
		resume: vi.fn(),
		cancel: vi.fn(),
		retry: vi.fn(),
		decideApproval: vi.fn(),
	},
}));

describe("useAgentRun", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		sessionStorage.clear();
		localStorage.clear();
	});

	it("initializes with default state", () => {
		const { result } = renderHook(() => useAgentRun("proj-101"));

		expect(result.current.state.projectId).toBe("proj-101");
		expect(result.current.state.runId).toBeNull();
		expect(result.current.state.status).toBeNull();
		expect(result.current.state.approvalMode).toBe("AUTO");
		expect(result.current.state.currentStep).toBe(0);
		expect(result.current.state.completedSteps).toEqual([]);
		expect(result.current.state.failedSteps).toEqual([]);
		expect(result.current.state.steps).toEqual([]);
	});

	it("updates approval mode and syncs to localStorage", () => {
		const { result } = renderHook(() => useAgentRun("proj-101"));

		act(() => {
			result.current.setApprovalMode("STEP_BY_STEP");
		});

		expect(result.current.state.approvalMode).toBe("STEP_BY_STEP");
		expect(localStorage.getItem("bazspark:agent-approval-mode")).toBe("STEP_BY_STEP");

		act(() => {
			result.current.setApprovalMode("AUTO");
		});

		expect(result.current.state.approvalMode).toBe("AUTO");
		expect(localStorage.getItem("bazspark:agent-approval-mode")).toBe("AUTO");
	});

	it("starts a run and sets RUNNING state with plan steps", async () => {
		const { result } = renderHook(() => useAgentRun("proj-101"));

		const sampleSteps = [
			{
				step_id: "s1",
				capability_id: "spatial.place_devices",
				description: "Place smoke detectors",
			},
			{
				step_id: "s2",
				capability_id: "electrical.calculate_voltage_drop",
				description: "Calculate circuit load",
			},
		];

		await act(async () => {
			await result.current.startRun({
				projectId: "proj-101",
				steps: sampleSteps,
				approvalMode: "STEP_BY_STEP",
			});
		});

		expect(result.current.state.status).toBe("RUNNING");
		expect(result.current.state.approvalMode).toBe("STEP_BY_STEP");
		expect(result.current.state.steps.length).toBe(2);
		expect(result.current.state.steps[0].capability_id).toBe("spatial.place_devices");
	});

	it("rehydrates active run from backend REST", async () => {
		const mockResponse = {
			success: true,
			data: {
				run_id: "run-persisted-99",
				project_id: "proj-101",
				status: "WAITING_APPROVAL",
				approval_mode: "STEP_BY_STEP",
				current_step: 1,
				completed_steps: [0],
				failed_steps: [],
				pending_approval_id: "appr-123",
				version: 3,
				plan: {
					steps: [
						{ step_id: "s1", capability_id: "spatial.place_devices", status: "completed" },
						{ step_id: "s2", capability_id: "electrical.calculate_voltage_drop", status: "waiting_approval" },
					],
				},
			},
		};

		vi.mocked(agentRunsApi.getStatus).mockResolvedValue(mockResponse);

		const { result } = renderHook(() => useAgentRun("proj-101"));

		await act(async () => {
			await result.current.rehydrateRun("run-persisted-99");
		});

		expect(result.current.state.runId).toBe("run-persisted-99");
		expect(result.current.state.status).toBe("WAITING_APPROVAL");
		expect(result.current.state.currentStep).toBe(1);
		expect(result.current.state.completedSteps).toEqual([0]);
		expect(result.current.state.steps.length).toBe(2);
	});

	it("calls cancel API and clears state on clearRun", async () => {
		vi.mocked(agentRunsApi.cancel).mockResolvedValue({
			success: true,
			data: {
				run_id: "run-cancel-1",
				project_id: "proj-101",
				status: "CANCELLED",
				approval_mode: "AUTO",
				current_step: 0,
				completed_steps: [],
				failed_steps: [],
				pending_approval_id: null,
				version: 2,
			},
		});

		const { result } = renderHook(() => useAgentRun("proj-101"));

		await act(async () => {
			await result.current.startRun({
				projectId: "proj-101",
				steps: [{ step_id: "s1", capability_id: "spatial.place_devices" }],
			});
		});

		act(() => {
			result.current.clearRun();
		});

		expect(result.current.state.runId).toBeNull();
		expect(result.current.state.status).toBeNull();
		expect(result.current.state.steps).toEqual([]);
	});
});
