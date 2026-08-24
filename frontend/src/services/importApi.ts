/**
 * frontend/src/services/importApi.ts
 * ===================================
 * API v2 client for Unified Ingestion & Import Orchestrator.
 *
 * Implements:
 *   - Drawing file staging / upload (.dwg, .dxf, .pdf, .ifc, .rvt, .xlsx, .csv)
 *   - Deterministic geometry and entity inspection
 *   - Revision-bound import planning
 *   - Atomic OCC execution and canonical database commit
 *   - Durable, policy-governed AgentRun pipeline initiation
 */

import { ApiClient } from "./apiClient";

export interface StagedFileRecord {
	file_id: string;
	original_filename: string;
	sanitized_filename: string;
	file_size_bytes: number;
	detected_format: "dwg" | "dxf" | "pdf" | "ifc" | "rvt" | "xlsx" | "csv" | "json";
	sha256_hash: string;
	staged_path: string;
	uploaded_by: string;
	created_at: string;
	metadata: Record<string, unknown>;
	status: "staged" | "inspected" | "imported" | "failed";
}

export interface InspectionResult {
	file_id: string;
	detected_format: string;
	confidence_score: number;
	rooms_count: number;
	devices_count: number;
	layers_count: number;
	extracted_entities: Record<string, unknown>;
	warnings: string[];
}

export interface ImportPlan {
	plan_id: string;
	file_id: string;
	project_id: string;
	expected_revision: number;
	detected_format: string;
	filename: string;
	estimated_rooms: number;
	estimated_devices: number;
	estimated_layers: number;
	warnings: string[];
	required_policy: "AUTO_APPROVED" | "REQUIRES_APPROVAL" | "MANDATORY_HUMAN_REVIEW";
	summary: string;
	created_at: string;
}

export interface ImportExecutionResult {
	import_id: string;
	file_id: string;
	project_id: string;
	previous_revision: number;
	new_revision: number;
	imported_rooms: number;
	imported_devices: number;
	imported_layers: number;
	audit_hash: string;
	warnings: string[];
	completed_at: string;
	success: boolean;
}

export interface AgentRunSummary {
	runId: string;
	status: "PLANNING" | "READY" | "RUNNING" | "WAITING_APPROVAL" | "COMPLETED" | "FAILED" | "CANCELLED" | "PAUSED";
	currentStep: string | null;
	completedSteps: string[];
	pendingApprovalId: string | null;
	projectId: string;
	approvalMode: "AUTO" | "STEP_BY_STEP";
}

export class ImportApiClient extends ApiClient {
	constructor() {
		super(import.meta.env.VITE_API_URL || "/api/v2");
	}

	/**
	 * Upload and stage a drawing / BIM file.
	 */
	async uploadDrawingFile(file: File): Promise<StagedFileRecord> {
		const formData = new FormData();
		formData.append("file", file, file.name);

		const res = await this.fetchWithRetry<{
			success: boolean;
			file: StagedFileRecord;
		}>(`${this.baseUrl}/import/upload`, {
			method: "POST",
			body: formData,
			// Empty Content-Type allows the browser/fetch to set multipart/form-data with boundary
			headers: {
				"Content-Type": "",
			},
		});
		return res.file;
	}

	/**
	 * Inspect a staged file and extract entity layout and metadata.
	 */
	async inspectStagedFile(fileId: string): Promise<InspectionResult> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			inspection: InspectionResult;
		}>(`${this.baseUrl}/import/inspect`, {
			method: "POST",
			body: JSON.stringify({ file_id: fileId }),
		});
		return res.inspection;
	}

	/**
	 * Construct a deterministic import plan bound to target project revision.
	 */
	async planImport(
		fileId: string,
		projectId = "default_project",
		options: Record<string, unknown> = {},
	): Promise<ImportPlan> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			plan: ImportPlan;
		}>(`${this.baseUrl}/import/plan`, {
			method: "POST",
			body: JSON.stringify({
				file_id: fileId,
				project_id: projectId,
				options,
			}),
		});
		return res.plan;
	}

	/**
	 * Atomically execute import and commit entities to canonical state with OCC check.
	 */
	async executeImport(
		fileId: string,
		projectId: string,
		expectedRevision: number,
		options: Record<string, unknown> = {},
	): Promise<ImportExecutionResult> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			result: ImportExecutionResult;
		}>(`${this.baseUrl}/import/execute`, {
			method: "POST",
			body: JSON.stringify({
				file_id: fileId,
				project_id: projectId,
				expected_revision: expectedRevision,
				options,
			}),
		});
		return res.result;
	}

	/**
	 * Initiate a durable, multi-step AgentRun for the import workflow.
	 */
	async createImportRun(
		fileId: string,
		projectId = "default_project",
		approvalMode: "AUTO" | "STEP_BY_STEP" = "AUTO",
		options: Record<string, unknown> = {},
	): Promise<AgentRunSummary> {
		const res = await this.fetchWithRetry<{
			success: boolean;
			run: AgentRunSummary;
		}>(`${this.baseUrl}/import/runs`, {
			method: "POST",
			body: JSON.stringify({
				file_id: fileId,
				project_id: projectId,
				approval_mode: approvalMode,
				options,
			}),
		});
		return res.run;
	}
}

export const importApi = new ImportApiClient();
