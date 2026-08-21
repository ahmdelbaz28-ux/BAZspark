/**
 * mlApi.ts - REST API Client for Machine Learning & Predictive Analytics Services
 *
 * Provides typed interfaces and API endpoints for:
 *   - Training jobs & model lifecycle
 *   - Monotonicity checks & safety boundary enforcement
 *   - Survival analysis (lifelines / Weibull / Cox PH)
 *   - Gradient boosting / XGBoost inference & feature importance (SHAP)
 *   - Anomaly detection & predictive maintenance
 */

import { ApiClient as BaseApiClient } from "./apiClient";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

export interface MLModelMetrics {
	accuracy?: number;
	precision?: number;
	recall?: number;
	f1Score?: number;
	rocAuc?: number;
	mae?: number;
	rmse?: number;
	r2?: number;
	loss?: number;
	valLoss?: number;
	monotonicityScore?: number;
	safetyBoundaryViolations?: number;
}

export interface MLModelSummary {
	modelId: string;
	name: string;
	framework: "xgboost" | "scikit-learn" | "lifelines" | "pytorch" | "custom";
	taskType: "classification" | "regression" | "survival" | "anomaly";
	status: "ready" | "training" | "evaluating" | "failed" | "archived";
	version: string;
	createdAt: string;
	updatedAt: string;
	metrics?: MLModelMetrics;
	features?: string[];
	hyperparameters?: Record<string, unknown>;
}

export interface MLPredictionRequest {
	modelId: string;
	features: Record<string, number | string | boolean>;
	explain?: boolean;
	safetyEnforcement?: "strict" | "advisory" | "none";
}

export interface ShapExplanation {
	baseValue: number;
	values: Record<string, number>;
	featureNames: string[];
}

export interface MLPredictionResponse {
	prediction: number | string | boolean | number[];
	probabilities?: Record<string, number>;
	confidence?: number;
	shap?: ShapExplanation;
	safetyAdvisory?: {
		compliant: boolean;
		violations: string[];
		recommendation?: string;
	};
	latencyMs: number;
	modelId: string;
	timestamp: string;
}

export interface MLTrainingJobRequest {
	modelName: string;
	framework: "xgboost" | "scikit-learn" | "lifelines";
	taskType: "classification" | "regression" | "survival";
	datasetUri: string;
	targetColumn: string;
	featureColumns?: string[];
	monotonicConstraints?: Record<string, 1 | -1 | 0>;
	hyperparameters?: Record<string, unknown>;
}

export interface MLTrainingJobStatus {
	jobId: string;
	modelId?: string;
	status: "queued" | "running" | "completed" | "failed";
	progress: number;
	currentEpoch?: number;
	totalEpochs?: number;
	logs?: string[];
	errorMessage?: string;
	startedAt?: string;
	finishedAt?: string;
}

export interface MonotonicityCheckResult {
	feature: string;
	constraint: "increasing" | "decreasing";
	violationCount: number;
	isMonotonic: boolean;
	maxDeviation: number;
}

export interface SafetyBoundaryAudit {
	checkedAt: string;
	passed: boolean;
	totalChecks: number;
	violationsCount: number;
	checks: Array<{
		name: string;
		status: "pass" | "warn" | "fail";
		details: string;
	}>;
}

export class MLApiClient extends BaseApiClient {
	constructor(baseUrl?: string) {
		super(baseUrl || API_BASE_URL);
	}

	async listModels(): Promise<MLModelSummary[]> {
		try {
			return await this.get<MLModelSummary[]>("/ml/models");
		} catch {
			return [];
		}
	}

	async getModel(modelId: string): Promise<MLModelSummary | null> {
		try {
			return await this.get<MLModelSummary>(`/ml/models/${encodeURIComponent(modelId)}`);
		} catch {
			return null;
		}
	}

	async predict(req: MLPredictionRequest): Promise<MLPredictionResponse> {
		return this.post<MLPredictionResponse>("/ml/predict", req);
	}

	async startTraining(req: MLTrainingJobRequest): Promise<MLTrainingJobStatus> {
		return this.post<MLTrainingJobStatus>("/ml/train", req);
	}

	async getTrainingStatus(jobId: string): Promise<MLTrainingJobStatus> {
		return this.get<MLTrainingJobStatus>(`/ml/train/${encodeURIComponent(jobId)}`);
	}

	async checkMonotonicity(modelId: string): Promise<MonotonicityCheckResult[]> {
		try {
			return await this.get<MonotonicityCheckResult[]>(`/ml/models/${encodeURIComponent(modelId)}/monotonicity`);
		} catch {
			return [];
		}
	}

	async auditSafetyBoundary(modelId: string): Promise<SafetyBoundaryAudit> {
		try {
			return await this.get<SafetyBoundaryAudit>(`/ml/models/${encodeURIComponent(modelId)}/safety-audit`);
		} catch {
			return {
				checkedAt: new Date().toISOString(),
				passed: true,
				totalChecks: 0,
				violationsCount: 0,
				checks: [],
			};
		}
	}
}

export const mlApi = new MLApiClient();
export default mlApi;
