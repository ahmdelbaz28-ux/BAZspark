/**
 * useSidebarBadges.ts — V270 FIX (audit "Hard-coded sidebar badges 3").
 *
 * The audit flagged three sidebar badges that were static strings:
 *   • "3"     on Conflicts       → should reflect actual conflict count
 *   • "safe"  on Physics Guards  → should reflect guard state from backend
 *   • "live"  on AI Agent        → should reflect agent activity status
 *
 * This hook polls the three backend endpoints (lightweight GETs) every 30s
 * and returns live values. On error, returns null (badge hidden) rather
 * than showing a stale hard-coded value.
 *
 * Endpoints used (all require MONITOR_READ / CONFLICT_READ / QOMN_READ):
 *   GET /api/v1/conflicts                  → paginated list with `total` count
 *   GET /api/v1/qomn/physics-guards        → array of guard definitions
 *   GET /api/v1/monitor/agent-activity     → agent activity log entries
 */

import { useEffect, useState } from "react";
import { apiCall } from "@/services/fullApi";

export interface SidebarBadgeState {
	/** Conflicts badge: count as string, or null if unavailable */
	conflicts: string | null;
	/** Physics Guards badge: "safe" if all guards pass, "violations: N" otherwise, or null */
	physicsGuards: string | null;
	/** AI Agent badge: "live" if recent activity, "idle" otherwise, or null */
	agentActivity: string | null;
}

const POLL_INTERVAL_MS = 30_000;
const RECENT_ACTIVITY_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

const INITIAL_STATE: SidebarBadgeState = {
	conflicts: null,
	physicsGuards: null,
	agentActivity: null,
};

async function fetchJson<T>(url: string): Promise<T | null> {
	try {
		// V271 FIX: use apiCall for unified auth header injection, retry,
		// and timeout. GET requests are CSRF-exempt but still benefit from
		// apiCall's auth + retry + 30s timeout — direct fetch() had none.
		return await apiCall<T>(url, { method: "GET" });
	} catch {
		return null;
	}
}

export function useSidebarBadges(): SidebarBadgeState {
	const [state, setState] = useState<SidebarBadgeState>(INITIAL_STATE);

	useEffect(() => {
		let cancelled = false;

		const poll = async () => {
			// Fire all three in parallel
			// V271 FIX: apiCall prepends /api/v1, so pass relative paths only.
			const [conflictsResp, guardsResp, agentResp] = await Promise.all([
				fetchJson<{ total?: number; data?: { total?: number } }>(
					"/conflicts?page=1&page_size=1"
				),
				fetchJson<{ data?: Array<{ violated?: boolean }> }>(
					"/qomn/physics-guards"
				),
				fetchJson<{ data?: Array<{ timestamp?: string; ts?: string }> }>(
					"/monitor/agent-activity?limit=1"
				),
			]);

			if (cancelled) return;

			// Conflicts count: prefer top-level total, fall back to data.total
			const conflictsTotal =
				conflictsResp?.total ?? conflictsResp?.data?.total ?? null;
			const conflictsBadge =
				conflictsTotal === null
					? null
					: conflictsTotal === 0
						? null
						: String(conflictsTotal);

			// Physics guards: count violations
			const guards = guardsResp?.data ?? [];
			const violations = guards.filter(g => g.violated === true).length;
			const physicsGuardsBadge =
				guards.length === 0
					? null
					: violations === 0
						? "safe"
						: `${violations} violations`;

			// Agent activity: any entry in last 5 min = "live", else "idle"
			const lastEntry = agentResp?.data?.[0];
			const lastTs = lastEntry?.timestamp ?? lastEntry?.ts;
			let agentBadge: string | null = null;
			if (lastTs) {
				const ageMs = Date.now() - new Date(lastTs).getTime();
				agentBadge = Number.isNaN(ageMs) ? null : ageMs < RECENT_ACTIVITY_THRESHOLD_MS ? "live" : "idle";
			}

			setState({
				conflicts: conflictsBadge,
				physicsGuards: physicsGuardsBadge,
				agentActivity: agentBadge,
			});
		};

		poll();
		const interval = window.setInterval(poll, POLL_INTERVAL_MS);

		return () => {
			cancelled = true;
			window.clearInterval(interval);
		};
	}, []);

	return state;
}
