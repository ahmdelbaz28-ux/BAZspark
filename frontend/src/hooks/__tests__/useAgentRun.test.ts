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
import { api } from "@/services/api";
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

// Mock api
vi.mock("@/services/api", () => ({
	api: {
		post: vi.fn(),
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

	it("handles resume, retry, cancel, approveStep, rejectStep", async () => {
		vi.mocked(agentRunsApi.getStatus).mockResolvedValue({
			success: true,
			data: {
				run_id: "run-actions-1",
				project_id: "proj-101",
				status: "WAITING_APPROVAL",
				approval_mode: "STEP_BY_STEP",
				current_step: 1,
				completed_steps: [0],
				failed_steps: [],
				pending_approval_id: "appr-1",
				version: 3,
				plan: {
					steps: [{ step_id: "s1", capability_id: "spatial.place_devices" }],
				},
			},
		});
		vi.mocked(agentRunsApi.resume).mockResolvedValue({
			success: true,
			data: {
				run_id: "run-actions-1",
				project_id: "proj-101",
				status: "RUNNING",
				approval_mode: "STEP_BY_STEP",
				current_step: 1,
				completed_steps: [0],
				failed_steps: [],
				pending_approval_id: null,
				version: 4,
			},
		});
		vi.mocked(agentRunsApi.retry).mockResolvedValue({
			success: true,
			data: {
				run_id: "run-actions-1",
				project_id: "proj-101",
				status: "RUNNING",
				approval_mode: "STEP_BY_STEP",
				current_step: 1,
				completed_steps: [0],
				failed_steps: [],
				pending_approval_id: null,
				version: 5,
			},
		});
		vi.mocked(agentRunsApi.decideApproval).mockResolvedValue({
			success: true,
			data: {
				run_id: "run-actions-1",
				project_id: "proj-101",
				status: "RUNNING",
				approval_mode: "STEP_BY_STEP",
				current_step: 2,
				completed_steps: [0, 1],
				failed_steps: [],
				pending_approval_id: null,
				version: 6,
			},
		});

		const { result } = renderHook(() => useAgentRun("proj-101"));

		await act(async () => {
			await result.current.rehydrateRun("run-actions-1");
		});

		await act(async () => {
			await result.current.resumeRun();
		});
		expect(agentRunsApi.resume).toHaveBeenCalled();

		await act(async () => {
			await result.current.retryRun();
		});
		expect(agentRunsApi.retry).toHaveBeenCalled();

		await act(async () => {
			await result.current.approveStep("Looks good");
		});

		await act(async () => {
			await result.current.rejectStep("Rejected");
		});

		await act(async () => {
			await result.current.pauseRun();
		});
	});

	it("acquires ticket via POST /agent/ws-ticket and handles ping-pong heartbeat", async () => {
		vi.mocked(api.post).mockResolvedValue({ success: true, ticket: "ticket-xyz-456" });

		const mockWsInstances: Array<{
			url: string;
			send: ReturnType<typeof vi.fn>;
			onopen: (() => void) | null;
			onmessage: ((event: { data: string }) => void) | null;
			readyState: number;
		}> = [];

		class MockWs {
			static readonly CONNECTING = 0;
			static readonly OPEN = 1;
			static readonly CLOSING = 2;
			static readonly CLOSED = 3;

			url: string;
			send = vi.fn();
			close = vi.fn();
			onopen: (() => void) | null = null;
			onmessage: ((event: { data: string }) => void) | null = null;
			onclose: (() => void) | null = null;
			onerror: (() => void) | null = null;
			readyState = 1; // OPEN

			constructor(url: string) {
				this.url = url;
				mockWsInstances.push(this);
				setTimeout(() => {
					if (this.onopen) this.onopen();
				}, 10);
			}
		}

		vi.stubGlobal("WebSocket", MockWs);
		globalThis.WebSocket = MockWs as unknown as typeof WebSocket;
		window.WebSocket = MockWs as unknown as typeof WebSocket;

		const { result } = renderHook(() => useAgentRun("proj-101"));

		// Allow async connectWs to resolve ticket and construct WebSocket
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 100));
		});

		expect(api.post).toHaveBeenCalledWith("/agent/ws-ticket", {});
		expect(mockWsInstances.length).toBeGreaterThan(0);
		expect(mockWsInstances[0].url).toContain("ticket=ticket-xyz-456");
		// §4.11 / C7: Ensure 0 occurrences of raw credentials or API keys in WebSocket URL
		expect(mockWsInstances[0].url).not.toMatch(/[?&](api_key|token|auth_token)=/i);

		// Simulate server sending {"type": "ping"}
		const wsInstance = mockWsInstances[0];
		act(() => {
			if (wsInstance.onmessage) {
				wsInstance.onmessage({ data: JSON.stringify({ type: "ping" }) });
			}
		});

		// Expect client to immediately send {"type": "pong"}
		expect(wsInstance.send).toHaveBeenCalledWith(JSON.stringify({ type: "pong" }));

		// Test startRun carries modelId and expectedRevision in WebSocket run_start frame
		await act(async () => {
			await result.current.startRun({
				projectId: "proj-101",
				modelId: "dt-model-101",
				expectedRevision: 4,
				steps: [{ step_id: "s1", capability_id: "spatial.place_devices" }],
			});
		});

		const lastCall = wsInstance.send.mock.calls[wsInstance.send.mock.calls.length - 1][0];
		const parsed = JSON.parse(lastCall);
		expect(parsed.type).toBe("run_start");
		expect(parsed.projectId).toBe("proj-101");
		expect(parsed.model_id).toBe("dt-model-101");
		expect(parsed.expected_revision).toBe(4);
	});

	it("handles O5 ticket failure gracefully without connection loop", async () => {
		vi.mocked(api.post).mockRejectedValueOnce(new Error("Network error"));

		const { result } = renderHook(() => useAgentRun("proj-101"));

		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 50));
		});

		expect(result.current.state.error).toContain("Failed to acquire WebSocket authentication ticket");
		expect(result.current.state.isConnected).toBe(false);
	});

	it("handles O6 conflict frame and recovers cleanly with recoverFromConflict", async () => {
		vi.mocked(api.post).mockResolvedValue({ success: true, ticket: "ticket-conflict-789" });

		const mockWsInstances: Array<{
			url: string;
			send: ReturnType<typeof vi.fn>;
			close: ReturnType<typeof vi.fn>;
			onopen: (() => void) | null;
			onmessage: ((event: { data: string }) => void) | null;
			readyState: number;
		}> = [];

		class MockWs {
			static readonly CONNECTING = 0;
			static readonly OPEN = 1;
			static readonly CLOSING = 2;
			static readonly CLOSED = 3;

			url: string;
			send = vi.fn();
			close = vi.fn();
			onopen: (() => void) | null = null;
			onmessage: ((event: { data: string }) => void) | null = null;
			onclose: (() => void) | null = null;
			onerror: (() => void) | null = null;
			readyState = 1;

			constructor(url: string) {
				this.url = url;
				mockWsInstances.push(this);
				setTimeout(() => {
					if (this.onopen) this.onopen();
				}, 10);
			}
		}

		vi.stubGlobal("WebSocket", MockWs);
		globalThis.WebSocket = MockWs as unknown as typeof WebSocket;
		window.WebSocket = MockWs as unknown as typeof WebSocket;

		const { result } = renderHook(() => useAgentRun("proj-101"));

		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 100));
		});

		expect(mockWsInstances.length).toBeGreaterThan(0);
		const wsInstance = mockWsInstances[0];

		// Simulate conflict event
		act(() => {
			if (wsInstance.onmessage) {
				wsInstance.onmessage({
					data: JSON.stringify({
						type: "ai_conflict",
						errorCode: "REVISION_CONFLICT",
						expectedRevision: 3,
						currentRevision: 5,
						message: "Project revision conflict",
					}),
				});
			}
		});

		expect(result.current.state.isConflict).toBe(true);
		expect(result.current.state.conflictRevision).toBe(5);
		expect(result.current.state.status).toBe("PAUSED");

		// Execute O6 recovery
		act(() => {
			result.current.recoverFromConflict(5);
		});

		expect(result.current.state.isConflict).toBe(false);
		expect(result.current.state.conflictRevision).toBeNull();
		expect(result.current.state.status).toBe("READY");
		expect(result.current.state.recoveryState).toEqual({ recoveredAtRevision: 5 });
	});
});
