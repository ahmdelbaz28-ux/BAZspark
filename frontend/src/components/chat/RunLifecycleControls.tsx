/**
 * RunLifecycleControls.tsx — Contextual Lifecycle Action Controls (Phase 2).
 *
 * Exposes server-authoritative controls: Cancel, Pause, Resume, Retry, Clear
 * based on the active Agent Run status.
 */
import {
	Ban,
	Loader2,
	Play,
	Plus,
	RotateCcw,
} from "lucide-react";
import type React from "react";
import type { AgentRunStatus } from "@/hooks/useAgentRun";

interface RunLifecycleControlsProps {
	status: AgentRunStatus | null;
	isActionPending: boolean;
	onPause: () => Promise<void>;
	onResume: () => Promise<void>;
	onCancel: () => Promise<void>;
	onRetry: () => Promise<void>;
	onClear: () => void;
}

export const RunLifecycleControls: React.FC<RunLifecycleControlsProps> = ({
	status,
	isActionPending,
	onPause: _onPause,
	onResume,
	onCancel,
	onRetry,
	onClear,
}) => {
	if (!status) return null;

	return (
		<div
			className="flex items-center justify-end gap-2 p-2 rounded-xl bg-card/80 border border-border/60 backdrop-blur-sm"
			data-testid="run-lifecycle-controls"
		>
			{/* Resume Button (When PAUSED) */}
			{status === "PAUSED" && (
				<button
					type="button"
					onClick={() => void onResume()}
					disabled={isActionPending}
					className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 text-emerald-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
					data-testid="lifecycle-resume-btn"
				>
					{isActionPending ? (
						<Loader2 className="h-3.5 w-3.5 animate-spin" />
					) : (
						<Play className="h-3.5 w-3.5" />
					)}
					Resume Run
				</button>
			)}

			{/* Retry Button (When FAILED) */}
			{status === "FAILED" && (
				<button
					type="button"
					onClick={() => void onRetry()}
					disabled={isActionPending}
					className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-secondary text-secondary-foreground hover:bg-secondary/90 disabled:opacity-50 transition-colors"
					data-testid="lifecycle-retry-btn"
				>
					{isActionPending ? (
						<Loader2 className="h-3.5 w-3.5 animate-spin" />
					) : (
						<RotateCcw className="h-3.5 w-3.5" />
					)}
					Retry Failed Step
				</button>
			)}

			{/* Cancel Button (When RUNNING, PAUSED, WAITING_APPROVAL, FAILED) */}
			{(status === "RUNNING" ||
				status === "PAUSED" ||
				status === "WAITING_APPROVAL" ||
				status === "FAILED") && (
				<button
					type="button"
					onClick={() => void onCancel()}
					disabled={isActionPending}
					className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-destructive/40 text-destructive hover:bg-destructive/10 disabled:opacity-50 transition-colors"
					data-testid="lifecycle-cancel-btn"
				>
					{isActionPending ? (
						<Loader2 className="h-3.5 w-3.5 animate-spin" />
					) : (
						<Ban className="h-3.5 w-3.5" />
					)}
					Cancel Run
				</button>
			)}

			{/* Clear / New Run Button (When COMPLETED or CANCELLED) */}
			{(status === "COMPLETED" || status === "CANCELLED") && (
				<button
					type="button"
					onClick={onClear}
					className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-muted text-foreground hover:bg-muted/80 transition-colors border border-border"
					data-testid="lifecycle-clear-btn"
				>
					<Plus className="h-3.5 w-3.5" />
					New Engineering Run
				</button>
			)}
		</div>
	);
};
