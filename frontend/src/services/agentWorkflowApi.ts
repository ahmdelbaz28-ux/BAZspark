/**
 * frontend/src/services/agentWorkflowApi.ts — Autonomous Engineering Workflow API Client (Phase 6).
 *
 * Provides typed, server-authoritative client functions for:
 * - Autonomous Workflow Planning (NL -> DAG Plan + Execution Policy Evaluation)
 * - Planned Workflow Execution (AgentRunOrchestrator dispatch)
 * - Durable Run Lifecycle Management (Status, Resume, Pause, Cancel, Retry, Approval Decisions)
 */

import { api } from "./api";

export interface PlannedStepRecord {
	step_id: string;
	capability_id: string;
	description: string;
	dependencies: string[];
	payload: Record<string, unknown>;
	risk_class: string;
	policy_result: string;
	requires_approval: boolean;
}

export interface AutonomousPlanRecord {
	plan_id: string;
	project_id: string;
	expected_revision: number;
	intent_summary: string;
	intent_category?: string;
	steps: PlannedStepRecord[];
	dag: {
		nodes:
			| Array<{
					node_id: string;
					capability_id: string;
					dependencies: string[];
					description?: string;
			  }>
			| Record<
					string,
					{
						node_id: string;
						capability_id: string;
						dependencies: string[];
						description?: string;
					}
			  >;
	};
	requires_human_approval: boolean;
	overall_policy_decision: string;
	projected_state: Record<string, unknown>;
	combined_audit_digest?: string;
	token_telemetry?: Record<string, unknown>;
	created_at?: string;
}

export interface AgentRunStateRecord {
	runId: string;
	projectId: string;
	status: string;
	approvalMode: string;
	currentStep: string | null;
	completedSteps: string[];
	failedSteps: string[];
	pendingApprovalId: string | null;
	recoveryState: Record<string, unknown>;
	auditReference: string;
	version: number;
}

export const agentWorkflowApi = {
	/**
	 * Synthesize an autonomous workflow plan from natural language or structured specifications.
	 */
	async planWorkflow(params: {
		prompt: string;
		projectId?: string;
		modelId?: string;
		entityId?: string;
		entityType?: string;
		expectedRevision?: number;
		compositeSpec?: Record<string, unknown>;
		approvalMode?: "AUTO" | "STEP_BY_STEP";
		governancePolicy?: Record<string, unknown>;
	}): Promise<AutonomousPlanRecord> {
		const res = await api.post<{ success: boolean; data: AutonomousPlanRecord }>("/workflow/runs/plan", {
			prompt: params.prompt,
			project_id: params.projectId || "",
			model_id: params.modelId || "",
			entity_id: params.entityId || "",
			entity_type: params.entityType || "",
			expected_revision: params.expectedRevision,
			composite_spec: params.compositeSpec,
			approval_mode: params.approvalMode || "AUTO",
			governance_policy: params.governancePolicy,
		});
		return res.data;
	},

	/**
	 * Plan and immediately dispatch an autonomous engineering workflow.
	 */
	async startPlannedWorkflow(params: {
		prompt: string;
		projectId?: string;
		modelId?: string;
		entityId?: string;
		entityType?: string;
		expectedRevision?: number;
		compositeSpec?: Record<string, unknown>;
		approvalMode?: "AUTO" | "STEP_BY_STEP";
		conversationId?: string;
		governancePolicy?: Record<string, unknown>;
	}): Promise<{ run: AgentRunStateRecord; plan: AutonomousPlanRecord }> {
		const res = await api.post<{
			success: boolean;
			data: AgentRunStateRecord;
			plan: AutonomousPlanRecord;
		}>("/workflow/runs/start-plan", {
			prompt: params.prompt,
			project_id: params.projectId || "",
			model_id: params.modelId || "",
			entity_id: params.entityId || "",
			entity_type: params.entityType || "",
			expected_revision: params.expectedRevision,
			composite_spec: params.compositeSpec,
			approval_mode: params.approvalMode || "AUTO",
			conversation_id: params.conversationId || "",
			governance_policy: params.governancePolicy,
		});
		return { run: res.data, plan: res.plan };
	},

	/**
	 * Get persisted status for an Agent Run.
	 */
	async getRunStatus(runId: string): Promise<AgentRunStateRecord> {
		const res = await api.get<{ success: boolean; data: AgentRunStateRecord }>(`/workflow/runs/${runId}/status`);
		return res.data;
	},

	/**
	 * Resume a paused or interrupted Agent Run.
	 */
	async resumeRun(runId: string): Promise<AgentRunStateRecord> {
		const res = await api.post<{ success: boolean; data: AgentRunStateRecord }>(`/workflow/runs/${runId}/resume`, {});
		return res.data;
	},

	/**
	 * Cancel an active Agent Run server-side.
	 */
	async cancelRun(runId: string): Promise<AgentRunStateRecord> {
		const res = await api.post<{ success: boolean; data: AgentRunStateRecord }>(`/workflow/runs/${runId}/cancel`, {});
		return res.data;
	},

	/**
	 * Retry a failed Agent Run from its failed step with idempotency protection.
	 */
	async retryRun(runId: string): Promise<AgentRunStateRecord> {
		const res = await api.post<{ success: boolean; data: AgentRunStateRecord }>(`/workflow/runs/${runId}/retry`, {});
		return res.data;
	},

	/**
	 * Record a human approval decision for a pending Agent Run step.
	 */
	async decideApproval(
		runId: string,
		approvalId: string,
		decision: "APPROVED" | "REJECTED",
		reason?: string,
	): Promise<AgentRunStateRecord> {
		const res = await api.post<{ success: boolean; data: AgentRunStateRecord }>(
			`/workflow/runs/${runId}/approvals/${approvalId}/decide`,
			{ decision, reason },
		);
		return res.data;
	},
};
