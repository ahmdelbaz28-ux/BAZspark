/**
 * useAgentRun.ts — Server-Authoritative Agent Run Lifecycle Hook (Phase 2).
 *
 * Implements:
 * - State machine: PLANNING → READY → RUNNING → WAITING_APPROVAL → PAUSED → FAILED → CANCELLED → COMPLETED
 * - Modes: AUTO vs STEP_BY_STEP (backend-backed execution policy)
 * - WebSocket real-time event streaming + bounded backoff reconnection
 * - Refresh-safe state rehydration from backend REST /workflow/runs/{id}/status
 * - Idempotency & safe retry/resume/cancel/approval controls
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { agentRunsApi, type AgentRunResponse } from "@/services/fullApi";

export type AgentRunStatus =
	| "PLANNING"
	| "READY"
	| "RUNNING"
	| "WAITING_APPROVAL"
	| "PAUSED"
	| "FAILED"
	| "CANCELLED"
	| "COMPLETED";

export type ApprovalMode = "AUTO" | "STEP_BY_STEP";

export interface AgentRunStep {
	step_id: string;
	capability_id: string;
	description?: string;
	status?: "pending" | "running" | "completed" | "waiting_approval" | "failed" | "skipped";
	payload?: Record<string, unknown>;
	result_data?: Record<string, unknown>;
	error_message?: string;
}

export interface PolicyResult {
	risk_class?: "READ" | "REVERSIBLE_VISUAL" | "ENGINEERING_MUTATION" | "SAFETY_CRITICAL" | string;
	approval_required?: boolean;
	reason?: string;
	validation_status?: "PASSED" | "WARNING" | "BLOCKED" | string;
	expected_impact?: string;
	[key: string]: unknown;
}

export interface PendingApprovalData {
	approvalId: string;
	runId: string;
	stepId: string;
	projectId: string;
	projectRevision: number;
	capabilityId: string;
	policyResult: PolicyResult;
	stepPayloadHash?: string;
}

export interface AgentRunState {
	runId: string | null;
	projectId: string;
	status: AgentRunStatus | null;
	approvalMode: ApprovalMode;
	currentStep: number;
	completedSteps: number[];
	failedSteps: number[];
	pendingApproval: PendingApprovalData | null;
	steps: AgentRunStep[];
	recoveryState: Record<string, unknown>;
	auditReference: string | null;
	version: number;
	error: string | null;
	elapsedSeconds: number;
	isActionPending: boolean;
	isConnected: boolean;
	isReconnecting: boolean;
}

export interface StartRunOptions {
	projectId: string;
	steps: Array<{
		step_id: string;
		capability_id: string;
		description?: string;
		payload?: Record<string, unknown>;
	}>;
	approvalMode?: ApprovalMode;
	conversationId?: string;
	plan?: Record<string, unknown>;
	governancePolicy?: Record<string, unknown>;
}

export interface UseAgentRunReturn {
	state: AgentRunState;
	startRun: (options: StartRunOptions) => Promise<void>;
	pauseRun: () => Promise<void>;
	resumeRun: () => Promise<void>;
	cancelRun: () => Promise<void>;
	retryRun: () => Promise<void>;
	approveStep: (reason?: string) => Promise<void>;
	rejectStep: (reason?: string) => Promise<void>;
	setApprovalMode: (mode: ApprovalMode) => void;
	clearRun: () => void;
	rehydrateRun: (runId: string) => Promise<void>;
}

const STORAGE_ACTIVE_RUN_KEY = "bazspark:active-agent-run-id";
const STORAGE_APPROVAL_MODE_KEY = "bazspark:agent-approval-mode";

function getInitialApprovalMode(): ApprovalMode {
	try {
		const stored = localStorage.getItem(STORAGE_APPROVAL_MODE_KEY);
		return stored === "STEP_BY_STEP" ? "STEP_BY_STEP" : "AUTO";
	} catch {
		return "AUTO";
	}
}

function getStoredActiveRunId(): string | null {
	try {
		return sessionStorage.getItem(STORAGE_ACTIVE_RUN_KEY);
	} catch {
		return null;
	}
}

function setStoredActiveRunId(runId: string | null): void {
	try {
		if (runId) {
			sessionStorage.setItem(STORAGE_ACTIVE_RUN_KEY, runId);
		} else {
			sessionStorage.removeItem(STORAGE_ACTIVE_RUN_KEY);
		}
	} catch {
		// Silent fail if quota or security restricted
	}
}

export function useAgentRun(defaultProjectId: string = ""): UseAgentRunReturn {
	const [state, setState] = useState<AgentRunState>(() => ({
		runId: null,
		projectId: defaultProjectId,
		status: null,
		approvalMode: getInitialApprovalMode(),
		currentStep: 0,
		completedSteps: [],
		failedSteps: [],
		pendingApproval: null,
		steps: [],
		recoveryState: {},
		auditReference: null,
		version: 1,
		error: null,
		elapsedSeconds: 0,
		isActionPending: false,
		isConnected: false,
		isReconnecting: false,
	}));

	const [prevDefaultProjectId, setPrevDefaultProjectId] = useState(defaultProjectId);
	if (!state.runId && defaultProjectId !== prevDefaultProjectId) {
		setPrevDefaultProjectId(defaultProjectId);
		if (defaultProjectId !== state.projectId) {
			setState((prev) => ({ ...prev, projectId: defaultProjectId }));
		}
	}

	const wsRef = useRef<WebSocket | null>(null);
	const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const reconnectAttemptsRef = useRef(0);
	const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const activeRunIdRef = useRef<string | null>(null);

	// Sync activeRunId ref
	useEffect(() => {
		activeRunIdRef.current = state.runId;
	}, [state.runId]);

	// Elapsed execution timer
	useEffect(() => {
		if (state.status === "RUNNING") {
			if (!timerRef.current) {
				timerRef.current = setInterval(() => {
					setState((prev) => ({ ...prev, elapsedSeconds: prev.elapsedSeconds + 1 }));
				}, 1000);
			}
		} else {
			if (timerRef.current) {
				clearInterval(timerRef.current);
				timerRef.current = null;
			}
		}
		return () => {
			if (timerRef.current) {
				clearInterval(timerRef.current);
				timerRef.current = null;
			}
		};
	}, [state.status]);

	// Handle status update from backend frame or REST
	const applyRunUpdate = useCallback((update: Partial<AgentRunResponse> & { type?: string; pendingApproval?: PendingApprovalData | null }) => {
		setState((prev) => {
			const newRunId = update.run_id ?? prev.runId;
			const newStatus = (update.status?.toUpperCase() as AgentRunStatus) ?? prev.status;
			const newApprovalMode = (update.approval_mode?.toUpperCase() as ApprovalMode) ?? prev.approvalMode;
			const newCurrentStep = update.current_step !== undefined ? update.current_step : prev.currentStep;
			const newCompleted = update.completed_steps ?? prev.completedSteps;
			const newFailed = update.failed_steps ?? prev.failedSteps;
			const newPendingApprovalId = update.pending_approval_id;

			// Reconcile steps with backend statuses
			let updatedSteps = prev.steps;
			if (update.plan?.steps) {
				updatedSteps = update.plan.steps.map((s) => ({
					step_id: s.step_id,
					capability_id: s.capability_id,
					description: s.description,
					status: (s.status as AgentRunStep["status"]) || "pending",
					payload: (s.payload as Record<string, unknown>) || {},
					result_data: s.result_data,
					error_message: s.error_message,
				}));
			} else if (updatedSteps.length > 0) {
				updatedSteps = updatedSteps.map((step, idx) => {
					if (newCompleted.includes(idx)) {
						return { ...step, status: "completed" };
					}
					if (newFailed.includes(idx)) {
						return { ...step, status: "failed" };
					}
					if (idx === newCurrentStep) {
						if (newStatus === "WAITING_APPROVAL") return { ...step, status: "waiting_approval" };
						if (newStatus === "RUNNING") return { ...step, status: "running" };
					}
					return step;
				});
			}

			// Retain or clear pendingApproval
			let pendingApproval = prev.pendingApproval;
			if (update.pendingApproval !== undefined) {
				pendingApproval = update.pendingApproval;
			} else if (!newPendingApprovalId && newStatus !== "WAITING_APPROVAL") {
				pendingApproval = null;
			}

			// Persist or clean up active run in sessionStorage
			if (newRunId && newStatus !== "COMPLETED" && newStatus !== "CANCELLED") {
				setStoredActiveRunId(newRunId);
			} else if (newStatus === "COMPLETED" || newStatus === "CANCELLED") {
				setStoredActiveRunId(null);
			}

			return {
				...prev,
				runId: newRunId,
				projectId: update.project_id ?? prev.projectId,
				status: newStatus,
				approvalMode: newApprovalMode,
				currentStep: newCurrentStep,
				completedSteps: newCompleted,
				failedSteps: newFailed,
				pendingApproval,
				steps: updatedSteps,
				recoveryState: update.recovery_state ?? prev.recoveryState,
				auditReference: update.audit_reference ?? prev.auditReference,
				version: update.version ?? prev.version,
				error: update.error ?? null,
				isActionPending: false,
			};
		});
	}, []);

	// WebSocket message dispatcher
	const handleWsMessage = useCallback((event: MessageEvent) => {
		try {
			const data = JSON.parse(event.data);
			if (!data || typeof data !== "object") return;

			if (data.type === "run_status_update") {
				applyRunUpdate({
					run_id: data.runId,
					project_id: data.projectId,
					status: data.status,
					approval_mode: data.approvalMode,
					current_step: data.currentStep,
					completed_steps: data.completedSteps,
					failed_steps: data.failedSteps,
					pending_approval_id: data.pendingApprovalId,
					recovery_state: data.recoveryState,
					audit_reference: data.auditReference,
					version: data.version,
				});
			} else if (data.type === "approval_request") {
				const pa: PendingApprovalData = {
					approvalId: data.approvalId,
					runId: data.runId,
					stepId: data.stepId,
					projectId: data.projectId,
					projectRevision: data.projectRevision,
					capabilityId: data.capabilityId,
					policyResult: data.policyResult || {},
					stepPayloadHash: data.stepPayloadHash,
				};
				setState((prev) => ({
					...prev,
					status: "WAITING_APPROVAL",
					pendingApproval: pa,
					isActionPending: false,
				}));
			} else if (data.type === "run_error") {
				setState((prev) => ({
					...prev,
					status: "FAILED",
					error: data.message || data.errorCode || "Run execution error",
					isActionPending: false,
				}));
			}
		} catch {
			// Malformed frame ignore
		}
	}, [applyRunUpdate]);

	const connectWsRef = useRef<() => void>(() => {});

	// WebSocket connection setup
	const connectWs = useCallback(() => {
		if (wsRef.current?.readyState === WebSocket.OPEN) return;

		try {
			const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
			const host = window.location.host;
			const wsUrl = `${protocol}//${host}/api/v1/agent/ws`;

			const ws = new WebSocket(wsUrl);
			wsRef.current = ws;

			ws.onopen = () => {
				reconnectAttemptsRef.current = 0;
				setState((prev) => ({ ...prev, isConnected: true, isReconnecting: false }));

				// If there is an active run, request status resync
				if (activeRunIdRef.current) {
					ws.send(JSON.stringify({ type: "run_status", runId: activeRunIdRef.current }));
				}
			};

			ws.onmessage = handleWsMessage;

			ws.onclose = () => {
				setState((prev) => ({ ...prev, isConnected: false }));
				// Exponential backoff reconnect
				if (reconnectAttemptsRef.current < 8) {
					const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 10000);
					reconnectAttemptsRef.current += 1;
					setState((prev) => ({ ...prev, isReconnecting: true }));
					reconnectTimerRef.current = setTimeout(() => {
						connectWsRef.current();
					}, delay);
				}
			};

			ws.onerror = () => {
				setState((prev) => ({ ...prev, isConnected: false }));
			};
		} catch {
			// Connection errors are handled asynchronously in onerror/onclose
		}
	}, [handleWsMessage]);

	useEffect(() => {
		connectWsRef.current = connectWs;
	}, [connectWs]);

	// Initialize WebSocket and rehydrate on mount
	useEffect(() => {
		connectWs();

		// Rehydrate stored run if available
		const storedRunId = getStoredActiveRunId();
		if (storedRunId) {
			void (async () => {
				try {
					const res = await agentRunsApi.getStatus(storedRunId);
					if (res.success && res.data) {
						applyRunUpdate(res.data);
					}
				} catch {
					setStoredActiveRunId(null);
				}
			})();
		}

		return () => {
			if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
			if (wsRef.current) wsRef.current.close();
		};
	}, [connectWs, applyRunUpdate]);

	// Rehydrate run state explicitly
	const rehydrateRun = useCallback(async (runId: string) => {
		try {
			setState((prev) => ({ ...prev, isActionPending: true }));
			const res = await agentRunsApi.getStatus(runId);
			if (res.success && res.data) {
				applyRunUpdate(res.data);
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to rehydrate run status";
			setState((prev) => ({ ...prev, error: msg, isActionPending: false }));
		}
	}, [applyRunUpdate]);

	// Start run
	const startRun = useCallback(async (options: StartRunOptions) => {
		const steps: AgentRunStep[] = options.steps.map((s) => ({
			step_id: s.step_id,
			capability_id: s.capability_id,
			description: s.description,
			status: "pending",
			payload: s.payload || {},
		}));

		setState((prev) => ({
			...prev,
			projectId: options.projectId,
			status: "RUNNING",
			approvalMode: options.approvalMode || prev.approvalMode,
			currentStep: 0,
			completedSteps: [],
			failedSteps: [],
			pendingApproval: null,
			steps,
			elapsedSeconds: 0,
			error: null,
			isActionPending: true,
		}));

		const payload = {
			type: "run_start",
			projectId: options.projectId,
			steps: options.steps,
			approvalMode: options.approvalMode || state.approvalMode,
			conversationId: options.conversationId || `conv-${Date.now()}`,
			plan: options.plan,
			governancePolicy: options.governancePolicy,
		};

		if (wsRef.current?.readyState === WebSocket.OPEN) {
			wsRef.current.send(JSON.stringify(payload));
		} else {
			// Simulate transition if WS is offline (fallback / dev mode)
			setTimeout(() => {
				setState((prev) => ({
					...prev,
					runId: `run-local-${Date.now()}`,
					isActionPending: false,
				}));
			}, 300);
		}
	}, [state.approvalMode]);

	// Pause run
	const pauseRun = useCallback(async () => {
		if (!state.runId) return;
		setState((prev) => ({ ...prev, isActionPending: true }));
		if (wsRef.current?.readyState === WebSocket.OPEN) {
			wsRef.current.send(JSON.stringify({ type: "run_pause", runId: state.runId }));
		}
	}, [state.runId]);

	// Resume run
	const resumeRun = useCallback(async () => {
		if (!state.runId) return;
		setState((prev) => ({ ...prev, isActionPending: true }));
		try {
			if (wsRef.current?.readyState === WebSocket.OPEN) {
				wsRef.current.send(JSON.stringify({ type: "run_resume", runId: state.runId }));
			} else {
				const res = await agentRunsApi.resume(state.runId);
				if (res.success && res.data) applyRunUpdate(res.data);
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to resume run";
			setState((prev) => ({ ...prev, error: msg, isActionPending: false }));
		}
	}, [state.runId, applyRunUpdate]);

	// Cancel run
	const cancelRun = useCallback(async () => {
		if (!state.runId) return;
		setState((prev) => ({ ...prev, isActionPending: true }));
		try {
			if (wsRef.current?.readyState === WebSocket.OPEN) {
				wsRef.current.send(JSON.stringify({ type: "run_cancel", runId: state.runId }));
			} else {
				const res = await agentRunsApi.cancel(state.runId);
				if (res.success && res.data) applyRunUpdate(res.data);
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to cancel run";
			setState((prev) => ({ ...prev, error: msg, isActionPending: false }));
		}
	}, [state.runId, applyRunUpdate]);

	// Retry run
	const retryRun = useCallback(async () => {
		if (!state.runId) return;
		setState((prev) => ({ ...prev, isActionPending: true }));
		try {
			if (wsRef.current?.readyState === WebSocket.OPEN) {
				wsRef.current.send(JSON.stringify({ type: "run_retry", runId: state.runId }));
			} else {
				const res = await agentRunsApi.retry(state.runId);
				if (res.success && res.data) applyRunUpdate(res.data);
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to retry run";
			setState((prev) => ({ ...prev, error: msg, isActionPending: false }));
		}
	}, [state.runId, applyRunUpdate]);

	// Approve pending step
	const approveStep = useCallback(async (reason?: string) => {
		const approvalId = state.pendingApproval?.approvalId;
		const runId = state.runId;
		if (!approvalId || !runId) return;

		setState((prev) => ({ ...prev, isActionPending: true }));
		try {
			if (wsRef.current?.readyState === WebSocket.OPEN) {
				wsRef.current.send(
					JSON.stringify({
						type: "approval_decision",
						approvalId,
						decision: "APPROVED",
						reason: reason || "User approved from Chat Control Center",
					}),
				);
			} else {
				const res = await agentRunsApi.decideApproval(runId, approvalId, {
					decision: "APPROVED",
					reason,
				});
				if (res.success && res.data) applyRunUpdate(res.data);
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to approve step";
			setState((prev) => ({ ...prev, error: msg, isActionPending: false }));
		}
	}, [state.pendingApproval, state.runId, applyRunUpdate]);

	// Reject pending step
	const rejectStep = useCallback(async (reason?: string) => {
		const approvalId = state.pendingApproval?.approvalId;
		const runId = state.runId;
		if (!approvalId || !runId) return;

		setState((prev) => ({ ...prev, isActionPending: true }));
		try {
			if (wsRef.current?.readyState === WebSocket.OPEN) {
				wsRef.current.send(
					JSON.stringify({
						type: "approval_decision",
						approvalId,
						decision: "REJECTED",
						reason: reason || "User rejected from Chat Control Center",
					}),
				);
			} else {
				const res = await agentRunsApi.decideApproval(runId, approvalId, {
					decision: "REJECTED",
					reason,
				});
				if (res.success && res.data) applyRunUpdate(res.data);
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to reject step";
			setState((prev) => ({ ...prev, error: msg, isActionPending: false }));
		}
	}, [state.pendingApproval, state.runId, applyRunUpdate]);

	// Update approval mode
	const setApprovalMode = useCallback((mode: ApprovalMode) => {
		try {
			localStorage.setItem(STORAGE_APPROVAL_MODE_KEY, mode);
		} catch {
			// ignore
		}
		setState((prev) => ({ ...prev, approvalMode: mode }));
	}, []);

	// Clear run state
	const clearRun = useCallback(() => {
		setStoredActiveRunId(null);
		setState((prev) => ({
			...prev,
			runId: null,
			status: null,
			currentStep: 0,
			completedSteps: [],
			failedSteps: [],
			pendingApproval: null,
			steps: [],
			elapsedSeconds: 0,
			error: null,
			isActionPending: false,
		}));
	}, []);

	return {
		state,
		startRun,
		pauseRun,
		resumeRun,
		cancelRun,
		retryRun,
		approveStep,
		rejectStep,
		setApprovalMode,
		clearRun,
		rehydrateRun,
	};
}
