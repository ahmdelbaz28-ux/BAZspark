/**
 * WorkflowActionCard — Phase 3 (Workstation Cockpit)
 *
 * 5-state lifecycle card for the AI Workflow Surface:
 *   PLAN → PREVIEW → APPROVE → VERIFY → LINEAGE
 *
 * OCC Conflict: renders amber alert with Refresh/Discard actions when
 * CONCURRENCY_CONFLICT is detected (expectedRevision mismatch).
 */
import {
	AlertTriangle,
	BadgeCheck,
	CheckCircle2,
	ChevronRight,
	Circle,
	ClipboardCopy,
	Loader2,
	RefreshCcw,
	ShieldAlert,
	XCircle,
} from "lucide-react";
import type React from "react";
import { useCallback, useState } from "react";
import type {
	BatteryPreview,
	CircuitPreview,
	CompositeWorkflowPreview,
	HydraulicPreview,
	PreviewDevice,
	WorkflowStepResultPreview,
} from "@/contexts/AIControllerContext";

// ─── Types ────────────────────────────────────────────────────────────────────

export type WorkflowLifecycleState =
	| "PLAN"
	| "PREVIEW"
	| "APPROVE"
	| "VERIFY"
	| "LINEAGE"
	| "CONCURRENCY_CONFLICT"
	| "IDLE";

interface ComplianceBadge {
	label: string;
	passed: boolean;
}

export interface WorkflowActionCardProps {
	lifecycleState: WorkflowLifecycleState;
	isLoading?: boolean;
	/** PLAN: DAG topology — ordered list of [nodeId, capabilityId] pairs */
	dagNodes?: Array<{
		node_id: string;
		capability_id: string;
		description?: string;
	}>;
	/** PREVIEW: multi-domain impact data */
	previewDevices?: PreviewDevice[];
	circuitPreview?: CircuitPreview | null;
	hydraulicPreview?: HydraulicPreview | null;
	batteryPreview?: BatteryPreview | null;
	compositePreview?: CompositeWorkflowPreview | null;
	/** APPROVE: expected revision for OCC gate */
	expectedRevision?: number;
	/** VERIFY: compliance results */
	complianceBadges?: ComplianceBadge[];
	stepResults?: WorkflowStepResultPreview[];
	/** LINEAGE: audit hash + actor */
	auditDigest?: string;
	actorId?: string;
	committedAt?: string;
	/** Callbacks */
	onApprove?: () => Promise<void>;
	onReject?: () => void;
	onRefreshContext?: () => Promise<void>;
	onDiscard?: () => void;
}

// ─── Domain badge colours ──────────────────────────────────────────────────────

const DOMAIN_BADGE_CLASSES: Record<string, string> = {
	spatial: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
	electrical: "bg-amber-500/15 text-amber-300 border-amber-500/30",
	hydraulics: "bg-blue-500/15 text-blue-300 border-blue-500/30",
	battery: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};

function domainBadgeClass(capabilityId: string): string {
	const domain = capabilityId.split(".")[0] ?? "spatial";
	return (
		DOMAIN_BADGE_CLASSES[domain] ??
		"bg-slate-500/15 text-slate-300 border-slate-500/30"
	);
}

function domainLabel(capabilityId: string): string {
	const map: Record<string, string> = {
		"spatial.place_devices": "Spatial",
		"electrical.calculate_voltage_drop": "Voltage Drop",
		"electrical.calculate_battery": "Battery",
		"hydraulics.solve_darcy_weisbach": "Hydraulics",
	};
	return map[capabilityId] ?? capabilityId;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({
	children,
}) => (
	<p className="text-[10px] font-mono font-semibold tracking-widest text-muted-foreground uppercase mb-2">
		{children}
	</p>
);

const MetricRow: React.FC<{
	label: string;
	value: React.ReactNode;
	warn?: boolean;
}> = ({ label, value, warn }) => (
	<div className="flex items-center justify-between py-1 border-b border-border/40 last:border-0">
		<span className="text-xs text-muted-foreground">{label}</span>
		<span
			className={`text-xs font-mono font-semibold ${warn ? "text-red-400" : "text-foreground"}`}
		>
			{value}
		</span>
	</div>
);

// ─── PLAN state ───────────────────────────────────────────────────────────────

const PlanView: React.FC<{
	nodes: WorkflowActionCardProps["dagNodes"];
}> = ({ nodes }) => {
	if (!nodes?.length) {
		return (
			<div className="flex items-center justify-center h-16 text-muted-foreground text-xs">
				No workflow steps planned.
			</div>
		);
	}
	return (
		<div>
			<SectionLabel>Execution Topology</SectionLabel>
			<div className="flex flex-col gap-1.5">
				{nodes.map((node, idx) => (
					<div key={node.node_id} className="flex items-center gap-2">
						<span className="text-[10px] font-mono text-muted-foreground w-4 shrink-0">
							{idx + 1}.
						</span>
						<span
							className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${domainBadgeClass(node.capability_id)}`}
						>
							{domainLabel(node.capability_id)}
						</span>
						{node.description && (
							<span className="text-xs text-muted-foreground truncate flex-1">
								{node.description}
							</span>
						)}
						{idx < (nodes?.length ?? 0) - 1 && (
							<ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
						)}
					</div>
				))}
			</div>
		</div>
	);
};

// ─── PREVIEW state ────────────────────────────────────────────────────────────

const PreviewView: React.FC<{
	devices?: PreviewDevice[];
	circuit?: CircuitPreview | null;
	hydraulic?: HydraulicPreview | null;
	battery?: BatteryPreview | null;
}> = ({ devices, circuit, hydraulic, battery }) => (
	<div className="flex flex-col gap-3">
		<SectionLabel>Multi-Domain Impact</SectionLabel>
		{devices !== undefined && (
			<div>
				<p className="text-[10px] text-cyan-400 font-mono mb-1">Spatial</p>
				<MetricRow label="Proposed Devices" value={devices.length} />
			</div>
		)}
		{circuit && (
			<div>
				<p className="text-[10px] text-amber-400 font-mono mb-1">
					Voltage Drop
				</p>
				<MetricRow
					label="ΔV%"
					value={`${circuit.voltageDropPct.toFixed(2)}%`}
					warn={circuit.voltageDropPct > 5}
				/>
				<MetricRow
					label="Terminal V"
					value={`${circuit.terminalVoltageV.toFixed(2)} V`}
				/>
				<MetricRow label="Compliant" value={circuit.isCompliant ? "✓" : "✗"} />
			</div>
		)}
		{battery && (
			<div>
				<p className="text-[10px] text-violet-400 font-mono mb-1">Battery</p>
				<MetricRow
					label="Required Ah"
					value={`${battery.requiredAh.toFixed(2)} Ah`}
				/>
				{battery.installedAh !== undefined && (
					<MetricRow
						label="Installed Ah"
						value={`${battery.installedAh.toFixed(2)} Ah`}
						warn={!battery.isAdequate}
					/>
				)}
				<MetricRow
					label="Thermal Derating"
					value={`×${battery.temperatureDerating.toFixed(3)}`}
				/>
			</div>
		)}
		{hydraulic && (
			<div>
				<p className="text-[10px] text-blue-400 font-mono mb-1">Hydraulics</p>
				<MetricRow
					label="Flow Velocity"
					value={`${hydraulic.flowVelocityMS.toFixed(2)} m/s`}
					warn={hydraulic.flowVelocityMS > 5.0}
				/>
				<MetricRow
					label="ΔP"
					value={`${hydraulic.pressureLossPsi.toFixed(2)} psi`}
				/>
				<MetricRow
					label="Regime"
					value={hydraulic.flowRegime}
				/>
			</div>
		)}
	</div>
);

// ─── VERIFY state ─────────────────────────────────────────────────────────────

const VerifyView: React.FC<{
	badges?: ComplianceBadge[];
	steps?: WorkflowStepResultPreview[];
}> = ({ badges, steps }) => (
	<div className="flex flex-col gap-3">
		<SectionLabel>Compliance Verification</SectionLabel>
		{badges?.map((badge) => (
			<div
				key={badge.label}
				className={`flex items-center gap-2 px-3 py-2 rounded-md border text-xs font-semibold ${
					badge.passed
						? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
						: "bg-red-500/10 border-red-500/30 text-red-400"
				}`}
			>
				{badge.passed ? (
					<BadgeCheck className="h-3.5 w-3.5 shrink-0" />
				) : (
					<ShieldAlert className="h-3.5 w-3.5 shrink-0" />
				)}
				{badge.label}
			</div>
		))}
		{steps && steps.length > 0 && (
			<div className="mt-1">
				<SectionLabel>Step Results</SectionLabel>
				{steps.map((step) => (
					<div
						key={step.nodeId}
						className="flex items-center gap-2 py-1 text-xs border-b border-border/40 last:border-0"
					>
						{step.success ? (
							<CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />
						) : (
							<XCircle className="h-3 w-3 text-red-400 shrink-0" />
						)}
						<span className="text-muted-foreground font-mono text-[10px]">
							{step.capabilityId}
						</span>
						{step.errorMessage && (
							<span className="text-red-400 truncate text-[10px]">
								{step.errorMessage}
							</span>
						)}
					</div>
				))}
			</div>
		)}
	</div>
);

// ─── LINEAGE state ────────────────────────────────────────────────────────────

const LineageView: React.FC<{
	auditDigest?: string;
	actorId?: string;
	committedAt?: string;
}> = ({ auditDigest, actorId, committedAt }) => {
	const [copied, setCopied] = useState(false);

	const handleCopy = useCallback(() => {
		if (!auditDigest) return;
		void navigator.clipboard.writeText(auditDigest).then(() => {
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		});
	}, [auditDigest]);

	const displayDigest = auditDigest
		? `${auditDigest.slice(0, 16)}…${auditDigest.slice(-8)}`
		: "—";

	return (
		<div className="flex flex-col gap-3">
			<SectionLabel>Merkle Audit Lineage</SectionLabel>
			<div className="bg-slate-800/60 border border-border rounded-md p-3 space-y-2">
				<div className="flex items-center justify-between gap-2">
					<span className="text-[10px] font-mono text-muted-foreground">
						SHA-256
					</span>
					<button
						type="button"
						onClick={handleCopy}
						className="flex items-center gap-1 text-[10px] font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
						aria-label="Copy audit hash"
					>
						<code className="text-[10px]">{displayDigest}</code>
						<ClipboardCopy className="h-3 w-3" />
					</button>
				</div>
				{copied && (
					<p className="text-[10px] text-emerald-400 font-mono">
						Hash copied ✓
					</p>
				)}
				{actorId && (
					<MetricRow label="Actor" value={actorId} />
				)}
				{committedAt && (
					<MetricRow
						label="Committed"
						value={new Date(committedAt).toLocaleTimeString()}
					/>
				)}
			</div>
		</div>
	);
};

// ─── Main Component ───────────────────────────────────────────────────────────

const STATE_LABELS: Record<WorkflowLifecycleState, string> = {
	IDLE: "Idle",
	PLAN: "Plan",
	PREVIEW: "Preview",
	APPROVE: "Approve",
	VERIFY: "Verify",
	LINEAGE: "Lineage",
	CONCURRENCY_CONFLICT: "Conflict",
};

const STATE_ORDER: WorkflowLifecycleState[] = [
	"PLAN",
	"PREVIEW",
	"APPROVE",
	"VERIFY",
	"LINEAGE",
];

export const WorkflowActionCard: React.FC<WorkflowActionCardProps> = ({
	lifecycleState,
	isLoading = false,
	dagNodes,
	previewDevices,
	circuitPreview,
	hydraulicPreview,
	batteryPreview,
	compositePreview,
	expectedRevision,
	complianceBadges,
	stepResults,
	auditDigest,
	actorId,
	committedAt,
	onApprove,
	onReject,
	onRefreshContext,
	onDiscard,
}) => {
	const [approving, setApproving] = useState(false);
	const [refreshing, setRefreshing] = useState(false);

	const handleApprove = useCallback(async () => {
		if (!onApprove) return;
		setApproving(true);
		try {
			await onApprove();
		} finally {
			setApproving(false);
		}
	}, [onApprove]);

	const handleRefresh = useCallback(async () => {
		if (!onRefreshContext) return;
		setRefreshing(true);
		try {
			await onRefreshContext();
		} finally {
			setRefreshing(false);
		}
	}, [onRefreshContext]);

	// ── OCC Conflict banner ──────────────────────────────────────────────────
	if (lifecycleState === "CONCURRENCY_CONFLICT") {
		return (
			<div
				className="workflow-action-card rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-3"
				data-testid="workflow-card-conflict"
				role="alert"
			>
				<div className="flex items-center gap-2 text-amber-400">
					<AlertTriangle className="h-4 w-4 shrink-0" />
					<span className="text-xs font-semibold">Concurrency Conflict</span>
				</div>
				<p className="text-xs text-muted-foreground leading-relaxed">
					The project was modified by another session. The current proposal is
					based on an outdated revision (N={expectedRevision ?? "?"}).
				</p>
				<div className="flex flex-col gap-2">
					<button
						type="button"
						onClick={() => void handleRefresh()}
						disabled={refreshing}
						className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-md bg-amber-500 text-amber-950 text-xs font-semibold hover:bg-amber-400 disabled:opacity-60 transition-colors"
					>
						{refreshing ? (
							<Loader2 className="h-3 w-3 animate-spin" />
						) : (
							<RefreshCcw className="h-3 w-3" />
						)}
						Refresh Context & Re-plan
					</button>
					<button
						type="button"
						onClick={onDiscard}
						className="w-full px-3 py-2 rounded-md border border-border text-xs text-muted-foreground hover:text-foreground hover:border-border/80 transition-colors"
					>
						Discard Proposal
					</button>
				</div>
			</div>
		);
	}

	// ── IDLE ──────────────────────────────────────────────────────────────────
	if (lifecycleState === "IDLE") {
		return (
			<div
				className="workflow-action-card rounded-xl border border-border bg-card p-4 flex items-center justify-center min-h-[80px]"
				data-testid="workflow-card-idle"
			>
				<p className="text-xs text-muted-foreground">
					Send an intent to begin workflow planning.
				</p>
			</div>
		);
	}

	// ── Active lifecycle step progress ────────────────────────────────────────
	const currentIdx = STATE_ORDER.indexOf(lifecycleState);

	return (
		<div
			className="workflow-action-card rounded-xl border border-border bg-card overflow-hidden"
			data-testid={`workflow-card-${lifecycleState.toLowerCase()}`}
		>
			{/* Header — step progress (UX: progress indicator for multi-step process, WCAG 2.2) */}
			<nav
				className="flex items-center gap-1 px-4 py-3 border-b border-border bg-card/80"
				aria-label="Workflow progress"
			>
				{STATE_ORDER.map((state, idx) => {
					const isDone = idx < currentIdx;
					const isActive = idx === currentIdx;
					return (
						<div key={state} className="flex items-center gap-1">
							<div
								className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold transition-colors ${
									isActive
										? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
										: isDone
											? "bg-emerald-500/15 text-emerald-400"
											: "text-muted-foreground"
								}`}
								aria-current={isActive ? "step" : undefined}
								aria-label={`${STATE_LABELS[state]}${isDone ? " (completed)" : isActive ? " (current)" : " (pending)"}`}
							>
								{isDone ? (
									<Circle className="h-2 w-2 fill-emerald-400 text-emerald-400" aria-hidden="true" />
								) : isActive && isLoading ? (
									<Loader2 className="h-2 w-2 animate-spin" aria-hidden="true" />
								) : (
									<Circle className="h-2 w-2" aria-hidden="true" />
								)}
								{STATE_LABELS[state]}
							</div>
							{idx < STATE_ORDER.length - 1 && (
								<div
									className={`w-3 h-px ${isDone ? "bg-emerald-400/50" : "bg-border"}`}
									aria-hidden="true"
								/>
							)}
						</div>
					);
				})}
			</nav>

			{/* Content */}
			<div className="p-4 space-y-3">
				{lifecycleState === "PLAN" && <PlanView nodes={dagNodes} />}

				{lifecycleState === "PREVIEW" && (
					<PreviewView
						devices={previewDevices ?? compositePreview?.projectedState.devices}
						circuit={circuitPreview}
						hydraulic={hydraulicPreview}
						battery={batteryPreview}
					/>
				)}

				{lifecycleState === "APPROVE" && (
					<div className="space-y-3">
						<SectionLabel>Single-Action Commit Gate</SectionLabel>
						{expectedRevision !== undefined && (
							<div className="text-[10px] font-mono text-muted-foreground">
								Expected revision:{" "}
								<span className="text-cyan-400">N={expectedRevision}</span>
							</div>
						)}
						<p className="text-xs text-muted-foreground leading-relaxed">
							Approving will atomically commit the proposed changes. This action
							is deterministic and traceable via SHA-256 audit chain.
						</p>
					</div>
				)}

				{lifecycleState === "VERIFY" && (
					<VerifyView
						badges={complianceBadges}
						steps={stepResults}
					/>
				)}

				{lifecycleState === "LINEAGE" && (
					<LineageView
						auditDigest={
							auditDigest ?? compositePreview?.combinedAuditDigest
						}
						actorId={actorId}
						committedAt={committedAt}
					/>
				)}
			</div>

			{/* Footer actions */}
			{(lifecycleState === "PLAN" ||
				lifecycleState === "PREVIEW" ||
				lifecycleState === "APPROVE") && (
				<div className="px-4 pb-4 flex items-center gap-2">
					{lifecycleState === "APPROVE" && (
						<button
							type="button"
							id="workflow-approve-btn"
							onClick={() => void handleApprove()}
							disabled={approving || isLoading}
							aria-describedby={expectedRevision !== undefined ? "workflow-revision-info" : undefined}
							className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-cyan-500 text-slate-950 text-xs font-bold hover:bg-cyan-400 disabled:opacity-60 transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-background"
						>
							{approving ? (
								<Loader2 className="h-3 w-3 animate-spin" />
							) : (
								<CheckCircle2 className="h-3 w-3" />
							)}
							Approve & Commit
						</button>
					)}
					{onReject && (
						<button
							type="button"
							id="workflow-reject-btn"
							onClick={onReject}
							disabled={approving}
							className="px-3 py-2 rounded-md border border-border text-xs text-muted-foreground hover:text-foreground hover:border-border/80 transition-colors"
						>
							Discard
						</button>
					)}
				</div>
			)}
		</div>
	);
};

export default WorkflowActionCard;
