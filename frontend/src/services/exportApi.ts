/**
 * frontend/src/services/exportApi.ts
 * ===================================
 * API v2 client for Unified Export & Bidirectional Engineering Orchestrator.
 *
 * Implements:
 *   - Export planning & loss/mapping report generation (.dxf, .revit, .ifc, .xlsx, .csv, .json, .pdf)
 *   - Deterministic execution with OCC revision check
 *   - Policy-governed AgentRun pipeline initiation
 *   - Export artifact metadata retrieval and secure download URL construction
 */

import { ApiClient } from "./apiClient";

export type ExportTargetFormat = "dxf" | "revit" | "ifc" | "xlsx" | "csv" | "json" | "pdf";

export interface ExportMappingReport {
	target_format: string;
	status: "LOSSLESS" | "PARTIALLY_LOSSLESS" | "LOSSY" | "UNSUPPORTED_MAPPING";
	mapped_entities: number;
	dropped_attributes: string[];
	transformed_entities: string[];
	warnings: string[];
}

export interface ExportPlan {
	plan_id: string;
	project_id: string;
	expected_revision: number;
	target_format: ExportTargetFormat;
	mapping_status: "LOSSLESS" | "PARTIALLY_LOSSLESS" | "LOSSY" | "UNSUPPORTED_MAPPING";
	mapping_report: ExportMappingReport;
	estimated_devices: number;
	estimated_connections: number;
	estimated_rooms: number;
	required_policy: "AUTO_APPROVED" | "REQUIRES_APPROVAL" | "MANDATORY_HUMAN_REVIEW";
	summary: string;
	options: Record<string, unknown>;
	created_at: string;
}

export interface ExportArtifactRecord {
	artifact_id: string;
	project_id: string;
	revision: number;
	target_format: ExportTargetFormat;
	filename: string;
	file_size_bytes: number;
	sha256_hash: string;
	mapping_status: string;
	validation_status: "VALID" | "INVALID";
	created_by: string;
	created_at: string;
	download_url: string;
	metadata: Record<string, unknown>;
}

export interface ExportExecutionResult {
	export_id: string;
	artifact: ExportArtifactRecord;
	mapping_report: ExportMappingReport;
	audit_hash: string;
	completed_at: string;
	success: boolean;
}

export interface ExportAgentRunSummary {
	runId: string;
	status: "PLANNING" | "READY" | "RUNNING" | "WAITING_APPROVAL" | "COMPLETED" | "FAILED" | "CANCELLED" | "PAUSED";
	currentStep: string | null;
	completedSteps: string[];
	pendingApprovalId: string | null;
	projectId: string;
	approvalMode: "AUTO" | "STEP_BY_STEP";
	plan?: ExportPlan;
}

export class ExportApiClient extends ApiClient {
	constructor() {
		super(import.meta.env.VITE_API_URL || "/api/v2");
	}

	/**
	 * Create a deterministic export plan with loss / mapping impact analysis.
	 */
	async planExport(
		projectId: string,
		targetFormat: ExportTargetFormat,
		options: Record<string, unknown> = {},
	): Promise<ExportPlan> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			plan: ExportPlan;
		}>(`${this.baseUrl}/export/plan`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				project_id: projectId,
				target_format: targetFormat,
				options,
			}),
		});
		return res.plan;
	}

	/**
	 * Directly execute export generation with OCC revision guard.
	 */
	async executeExport(
		projectId: string,
		expectedRevision: number,
		targetFormat: ExportTargetFormat,
		options: Record<string, unknown> = {},
	): Promise<ExportExecutionResult> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			result: ExportExecutionResult;
		}>(`${this.baseUrl}/export/execute`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				project_id: projectId,
				expected_revision: expectedRevision,
				target_format: targetFormat,
				options,
			}),
		});
		return res.result;
	}

	/**
	 * Initiate a durable, policy-governed AgentRun for the export workflow.
	 */
	async createExportRun(
		projectId: string,
		targetFormat: ExportTargetFormat,
		approvalMode: "AUTO" | "STEP_BY_STEP" = "AUTO",
		options: Record<string, unknown> = {},
	): Promise<ExportAgentRunSummary> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			run: ExportAgentRunSummary;
		}>(`${this.baseUrl}/export/run`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				project_id: projectId,
				target_format: targetFormat,
				approval_mode: approvalMode,
				options,
			}),
		});
		return res.run;
	}

	/**
	 * Get artifact metadata and validation status.
	 */
	async getArtifact(artifactId: string): Promise<ExportArtifactRecord> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			artifact: ExportArtifactRecord;
		}>(`${this.baseUrl}/export/artifacts/${artifactId}`);
		return res.artifact;
	}

	/**
	 * Get download URL for an export artifact.
	 */
	getDownloadUrl(artifactId: string): string {
		return `${this.baseUrl}/export/artifacts/${artifactId}/download`;
	}
}

export const exportApi = new ExportApiClient();
