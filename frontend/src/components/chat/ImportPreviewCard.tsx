/**
 * ImportPreviewCard.tsx — Phase 3 Unified Import & Ingestion Preview Card.
 *
 * Provides rich visualization for inspected drawing / BIM files:
 * - Magic-byte detected format badge (.dwg, .dxf, .pdf, .ifc, .rvt, .xlsx, .csv)
 * - SHA-256 integrity fingerprint
 * - Entity metrics: extracted rooms, candidate devices, layer count, confidence score
 * - Revision transition preview (e.g. Rev 1 -> 2)
 * - Required governance policy indicator
 * - Actions: "Start Agent Import Run" & "Direct Commit"
 */

import {
	AlertTriangle,
	CheckCircle2,
	ChevronRight,
	FileCode,
	FileText,
	Fingerprint,
	ShieldAlert,
	Sparkles,
} from "lucide-react";
import type React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ImportPlan, StagedFileRecord } from "@/services/importApi";

export interface ImportPreviewCardProps {
	stagedFile: StagedFileRecord;
	plan?: ImportPlan | null;
	isExecuting?: boolean;
	onStartAgentRun: (stagedFile: StagedFileRecord, approvalMode: "AUTO" | "STEP_BY_STEP") => void;
	onDirectExecute?: (stagedFile: StagedFileRecord) => void;
	onDismiss?: () => void;
}

function getFormatBadgeColor(format: string): string {
	switch (format.toLowerCase()) {
		case "dwg":
			return "bg-blue-500/15 text-blue-400 border-blue-500/30";
		case "dxf":
			return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
		case "pdf":
			return "bg-red-500/15 text-red-400 border-red-500/30";
		case "ifc":
			return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
		case "rvt":
			return "bg-violet-500/15 text-violet-400 border-violet-500/30";
		case "xlsx":
		case "csv":
			return "bg-amber-500/15 text-amber-400 border-amber-500/30";
		default:
			return "bg-muted text-muted-foreground border-border";
	}
}

export const ImportPreviewCard: React.FC<ImportPreviewCardProps> = ({
	stagedFile,
	plan,
	isExecuting = false,
	onStartAgentRun,
	onDirectExecute,
	onDismiss,
}) => {
	const formatColor = getFormatBadgeColor(stagedFile.detected_format);

	return (
		<div
			className="rounded-xl border border-border/80 bg-card/95 p-4 shadow-lg backdrop-blur transition-all space-y-3"
			data-testid="import-preview-card"
		>
			{/* Header: File info & Detected Format */}
			<div className="flex items-center justify-between gap-2 border-b border-border/40 pb-2.5">
				<div className="flex items-center gap-2 min-w-0">
					{stagedFile.detected_format === "pdf" ? (
						<FileText className="h-5 w-5 text-red-400 shrink-0" />
					) : (
						<FileCode className="h-5 w-5 text-cyan-400 shrink-0" />
					)}
					<div className="min-w-0">
						<h4 className="text-sm font-semibold text-foreground truncate" title={stagedFile.sanitized_filename}>
							{stagedFile.sanitized_filename}
						</h4>
						<div className="flex items-center gap-2 text-[11px] text-muted-foreground font-mono">
							<span>{(stagedFile.file_size_bytes / 1024).toFixed(1)} KB</span>
							<span>•</span>
							<span className="flex items-center gap-1">
								<Fingerprint className="h-3 w-3 text-muted-foreground" />
								{stagedFile.sha256_hash.slice(0, 8)}…
							</span>
						</div>
					</div>
				</div>

				<div className="flex items-center gap-2">
					<Badge variant="outline" className={`font-mono text-xs uppercase px-2 py-0.5 ${formatColor}`}>
						{stagedFile.detected_format}
					</Badge>
					<Badge variant="secondary" className="text-[10px] uppercase font-mono">
						{stagedFile.status}
					</Badge>
				</div>
			</div>

			{/* Metrics Grid */}
			{plan && (
				<div className="grid grid-cols-3 gap-2 text-center py-1">
					<div className="rounded-lg bg-muted/40 p-2 border border-border/30">
						<span className="text-[10px] uppercase tracking-wider text-muted-foreground">Rooms</span>
						<p className="text-base font-bold text-foreground">{plan.estimated_rooms}</p>
					</div>
					<div className="rounded-lg bg-muted/40 p-2 border border-border/30">
						<span className="text-[10px] uppercase tracking-wider text-muted-foreground">Devices</span>
						<p className="text-base font-bold text-cyan-400">{plan.estimated_devices}</p>
					</div>
					<div className="rounded-lg bg-muted/40 p-2 border border-border/30">
						<span className="text-[10px] uppercase tracking-wider text-muted-foreground">Layers</span>
						<p className="text-base font-bold text-foreground">{plan.estimated_layers}</p>
					</div>
				</div>
			)}

			{/* Plan Summary & Revision */}
			{plan && (
				<div className="rounded-lg bg-muted/20 p-2.5 text-xs space-y-1.5 border border-border/40">
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="font-medium text-foreground">Target Project: {plan.project_id}</span>
						<span className="font-mono text-[11px] text-cyan-400">
							Rev {plan.expected_revision} → {plan.expected_revision + 1}
						</span>
					</div>
					<p className="text-muted-foreground leading-relaxed">{plan.summary}</p>

					{plan.warnings && plan.warnings.length > 0 && (
						<div className="flex items-start gap-1.5 text-amber-400 text-[11px] pt-1">
							<AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
							<span>{plan.warnings.join(", ")}</span>
						</div>
					)}
				</div>
			)}

			{/* Policy Banner */}
			{plan && (
				<div className="flex items-center justify-between text-[11px] px-1">
					<div className="flex items-center gap-1.5 text-muted-foreground">
						{plan.required_policy === "AUTO_APPROVED" ? (
							<CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
						) : (
							<ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
						)}
						<span>Governance: {plan.required_policy}</span>
					</div>
				</div>
			)}

			{/* Action Buttons */}
			<div className="flex items-center justify-end gap-2 pt-1">
				{onDismiss && (
					<Button variant="ghost" size="sm" onClick={onDismiss} disabled={isExecuting} className="text-xs">
						Dismiss
					</Button>
				)}

				{onDirectExecute && plan && (
					<Button
						variant="outline"
						size="sm"
						onClick={() => onDirectExecute(stagedFile)}
						disabled={isExecuting}
						className="text-xs"
						data-testid="direct-import-btn"
					>
						Direct Ingest
					</Button>
				)}

				<Button
					variant="default"
					size="sm"
					onClick={() => onStartAgentRun(stagedFile, "AUTO")}
					disabled={isExecuting}
					className="text-xs gap-1.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white shadow-sm"
					data-testid="start-import-run-btn"
				>
					<Sparkles className="h-3.5 w-3.5" />
					<span>Start Agent Import Run</span>
					<ChevronRight className="h-3.5 w-3.5 opacity-70" />
				</Button>
			</div>
		</div>
	);
};
