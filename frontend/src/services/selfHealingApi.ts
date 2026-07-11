/**
 * selfHealingApi.ts — Self-Healing Engine API client.
 *
 * V214: Exposes the 3 backend endpoints from backend/routers/self_healing.py:
 *   GET  /api/v1/self-healing/health  — CB + LRU + audit + LLM stats
 *   GET  /api/v1/self-healing/audit   — audit log entries + chain integrity
 *   POST /api/v1/self-healing/reset   — reset circuit breaker (admin)
 */

import { getApiKey } from "./apiKey";

const API_BASE = "/api/v1";

async function shApiCall<T>(
	path: string,
	options: RequestInit = {},
): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		...((options.headers as Record<string, string>) || {}),
	};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;

	const resp = await fetch(`${API_BASE}${path}`, {
		...options,
		headers,
		credentials: "same-origin",
	});
	if (!resp.ok) {
		const body = await resp.json().catch(() => ({}));
		throw new Error(body?.detail || `HTTP ${resp.status}: ${resp.statusText}`);
	}
	return resp.json();
}

export interface CircuitBreakerHealth {
	state: string;
	event_count: number;
	weighted_sum: number;
	threshold: number;
	window_seconds: number;
	utilization_pct: number;
	cooldown_seconds: number;
	half_open_max: number;
	half_open_count: number;
	seconds_since_open: number | null;
}

export interface LruCacheStats {
	hits: number;
	misses: number;
	evictions: number;
	size: number;
	maxsize: number;
}

export interface AuditLoggerStats {
	total_events: number;
	events_logged: number;
	file_path: string;
	file_size_bytes: number;
	rotation_count: number;
	last_event_time: string | null;
}

export interface LlmBreakerStats {
	max_rps: number;
	timeout: number;
	requests_allowed: number;
	requests_blocked: number;
}

export interface SelfHealingHealth {
	success: boolean;
	circuit_breaker: CircuitBreakerHealth;
	lru_cache: LruCacheStats;
	audit_logger: AuditLoggerStats;
	llm_breaker: LlmBreakerStats;
}

export interface AuditEntry {
	timestamp: string;
	function_name: string;
	error_type: string;
	error_message: string;
	tier_used: number;
	fix_applied: unknown;
	verification_result: string;
	before_hash: string;
	after_hash: string;
	hmac?: string;
	user_notification_status: string;
}

export interface SelfHealingAudit {
	success: boolean;
	stats: AuditLoggerStats;
	chain_integrity: { valid: boolean; error?: string };
	limit: number;
}

export const selfHealingApi = {
	getHealth: () => shApiCall<SelfHealingHealth>("/self-healing/health"),
	getAudit: (limit = 20) =>
		shApiCall<SelfHealingAudit>(`/self-healing/audit?limit=${limit}`),
	reset: () =>
		shApiCall<{ success: boolean; message: string; circuit_breaker: CircuitBreakerHealth }>(
			"/self-healing/reset",
			{ method: "POST" },
		),
};
