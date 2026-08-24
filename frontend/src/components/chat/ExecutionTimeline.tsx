/**
 * ExecutionTimeline.tsx — Compact Authoritative Execution Timeline (Phase 2).
 *
 * Renders the real-time execution lifecycle of a durable Agent Run:
 *   Plan → Context → Capability → Policy → Execution → Validation → Result
 * Displays individual step statuses, elapsed timer, and progress percentage.
 */
import {
	AlertCircle,
	BadgeCheck,
	CheckCircle2,
	Clock,
	Layers,
	Loader2,
	PauseCircle,
} from "lucide-react";
import type React from "react";
import type { AgentRunStatus, AgentRunStep } from "@/hooks/useAgentRun";

interface ExecutionTimelineProps {
	status: AgentRunStatus | null;
	currentStep: number;
	completedSteps: number[];
	failedSteps: number[];
	steps: AgentRunStep[];
	elapsedSeconds: number;
	runId?: string | null;
}

const LIFECYCLE_STAGES = [
	"Plan",
	"Context",
	"Capability",
	"Policy",
	"Execution",
	"Validation",
	"Result",
] as const;

function formatElapsed(seconds: number): string {
	const mins = Math.floor(seconds / 60);
	const secs = seconds % 60;
	return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({
	status,
	currentStep,
	completedSteps,
	failedSteps,
	steps,
	elapsedSeconds,
	runId,
}) => {
	if (!status || steps.length === 0) return null;

	const totalSteps = steps.length;
	const completedCount = completedSteps.length;
	const progressPct = totalSteps > 0 ? Math.round((completedCount / totalSteps) * 100) : 0;

	// Determine active lifecycle stage based on run status
	const getActiveStageIndex = (): number => {
		switch (status) {
			case "PLANNING":
				return 0;
			case "READY":
				return 1;
			case "RUNNING":
				return 4; // Execution
			case "WAITING_APPROVAL":
				return 3; // Policy gate
			case "COMPLETED":
				return 6; // Result
			case "FAILED":
			case "CANCELLED":
			case "PAUSED":
				return 4;
			default:
				return 0;
		}
	};

	const activeStageIdx = getActiveStageIndex();

	return (
		<div
			className="rounded-2xl border border-border/80 bg-card/60 backdrop-blur-md p-4 space-y-4 shadow-lg animate-in fade-in duration-200"
			data-testid="execution-timeline"
		>
			{/* Top Header: Run Status & Elapsed Time */}
			<div className="flex items-center justify-between border-b border-border/40 pb-3">
				<div className="flex items-center gap-2.5">
					<div className="w-8 h-8 rounded-lg bg-secondary/15 border border-secondary/30 flex items-center justify-center">
						<Layers className="h-4 w-4 text-secondary" />
					</div>
					<div>
						<div className="flex items-center gap-2">
							<span className="text-xs font-semibold text-foreground">
								Agent Execution Spine
							</span>
							<span
								className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
									status === "RUNNING"
										? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30 animate-pulse"
										: status === "WAITING_APPROVAL"
											? "bg-amber-500/15 text-amber-300 border-amber-500/30"
											: status === "COMPLETED"
												? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
												: status === "FAILED"
													? "bg-destructive/15 text-destructive border-destructive/30"
													: "bg-muted text-muted-foreground border-border"
								}`}
							>
								{status}
							</span>
						</div>
						{runId && (
							<p className="text-[10px] font-mono text-muted-foreground truncate max-w-[200px]">
								ID: {runId}
							</p>
						)}
					</div>
				</div>

				<div className="flex items-center gap-3">
					<div className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground bg-muted/40 px-2.5 py-1 rounded-md border border-border/30">
						<Clock className="h-3.5 w-3.5" />
						<span>{formatElapsed(elapsedSeconds)}</span>
					</div>
				</div>
			</div>

			{/* High-Level Lifecycle Breadcrumbs */}
			<div
				className="flex items-center justify-between gap-1 overflow-x-auto py-1"
				aria-label="Lifecycle progression"
			>
				{LIFECYCLE_STAGES.map((stage, idx) => {
					const isPast = idx < activeStageIdx || status === "COMPLETED";
					const isCurrent = idx === activeStageIdx && status !== "COMPLETED";

					return (
						<div key={stage} className="flex items-center gap-1 min-w-0 flex-1">
							<div
								className={`flex items-center justify-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono font-semibold w-full transition-colors truncate ${
									isCurrent
										? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
										: isPast
											? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
											: "bg-muted/30 text-muted-foreground/60 border border-transparent"
								}`}
								title={stage}
							>
								{isPast ? (
									<BadgeCheck className="h-3 w-3 shrink-0 text-emerald-400" />
								) : isCurrent && status === "RUNNING" ? (
									<Loader2 className="h-3 w-3 shrink-0 text-cyan-400 animate-spin" />
								) : null}
								<span className="truncate">{stage}</span>
							</div>
							{idx < LIFECYCLE_STAGES.length - 1 && (
								<div
									className={`w-2 h-px shrink-0 ${
										isPast ? "bg-emerald-500/40" : "bg-border/60"
									}`}
								/>
							)}
						</div>
					);
				})}
			</div>

			{/* Overall Progress Bar */}
			<div className="space-y-1.5">
				<div className="flex items-center justify-between text-[11px] text-muted-foreground">
					<span>
						Step {Math.min(currentStep + 1, totalSteps)} of {totalSteps}
					</span>
					<span className="font-mono font-semibold text-foreground">
						{progressPct}% Completed
					</span>
				</div>
				<div className="w-full h-1.5 rounded-full bg-muted/60 overflow-hidden">
					<div
						className={`h-full transition-all duration-300 ${
							status === "FAILED"
								? "bg-destructive"
								: status === "COMPLETED"
									? "bg-emerald-500"
									: "bg-gradient-to-r from-secondary to-cyan-400"
						}`}
						style={{ width: `${progressPct}%` }}
					/>
				</div>
			</div>

			{/* Granular Step List */}
			<div className="space-y-2 pt-1">
				<p className="text-[10px] font-mono font-semibold uppercase tracking-wider text-muted-foreground">
					Execution Steps
				</p>
				<div className="space-y-1.5">
					{steps.map((step, idx) => {
						const isDone = completedSteps.includes(idx);
						const isFailed = failedSteps.includes(idx);
						const isWaiting = idx === currentStep && status === "WAITING_APPROVAL";
						const isCurrent = idx === currentStep && status === "RUNNING";

						let itemBorderClass = "border-border/40 bg-card/40";
						if (isDone) itemBorderClass = "border-emerald-500/30 bg-emerald-500/5";
						if (isFailed) itemBorderClass = "border-destructive/40 bg-destructive/5";
						if (isWaiting) itemBorderClass = "border-amber-500/40 bg-amber-500/10 animate-pulse";
						if (isCurrent) itemBorderClass = "border-cyan-500/40 bg-cyan-500/10";

						return (
							<div
								key={step.step_id || `step-${idx}`}
								className={`flex items-center justify-between p-2.5 rounded-xl border transition-all ${itemBorderClass}`}
							>
								<div className="flex items-center gap-2.5 min-w-0">
									<div className="shrink-0">
										{isDone ? (
											<CheckCircle2 className="h-4 w-4 text-emerald-400" />
										) : isFailed ? (
											<AlertCircle className="h-4 w-4 text-destructive" />
										) : isWaiting ? (
											<PauseCircle className="h-4 w-4 text-amber-400" />
										) : isCurrent ? (
											<Loader2 className="h-4 w-4 text-cyan-400 animate-spin" />
										) : (
											<div className="w-4 h-4 rounded-full border-2 border-muted-foreground/40 flex items-center justify-center text-[9px] font-mono text-muted-foreground">
												{idx + 1}
											</div>
										)}
									</div>

									<div className="min-w-0">
										<div className="flex items-center gap-2">
											<span className="text-xs font-semibold text-foreground truncate">
												{step.description || `Step ${idx + 1}`}
											</span>
											<span className="text-[10px] font-mono px-1.5 py-0.2 rounded border bg-muted/40 text-muted-foreground border-border/50 shrink-0">
												{step.capability_id}
											</span>
										</div>
										{step.error_message && (
											<p className="text-[10px] text-destructive leading-tight mt-0.5 truncate">
												{step.error_message}
											</p>
										)}
									</div>
								</div>

								<div className="shrink-0 text-right">
									{isDone && (
										<span className="text-[10px] font-mono text-emerald-400">
											✓ Done
										</span>
									)}
									{isWaiting && (
										<span className="text-[10px] font-mono text-amber-400 font-bold">
											Paused for PE
										</span>
									)}
									{isCurrent && (
										<span className="text-[10px] font-mono text-cyan-400">
											Running…
										</span>
									)}
								</div>
							</div>
						);
					})}
				</div>
			</div>
		</div>
	);
};
