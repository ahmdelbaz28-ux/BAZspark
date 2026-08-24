/**
 * ExportPlanCard.tsx — Export Planning & Loss/Mapping Preview Card (Phase 4).
 *
 * Displays:
 * - Selected export format (DXF, Revit, IFC, XLSX, CSV, JSON, PDF)
 * - Authoritative project revision & OCC guard indicator
 * - Loss / Mapping analysis (LOSSLESS, PARTIALLY_LOSSLESS, LOSSY)
 * - Mapped entity counts and format transformation warnings
 * - Governed execution triggers (Direct Export vs Policy-Governed AgentRun)
 */

import {
	AlertTriangle,
	ArrowRight,
	CheckCircle2,
	Download,
	FileCode2,
	Info,
	Layers,
	ShieldAlert,
	ShieldCheck,
	Sparkles,
	X,
} from "lucide-react";
import type React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ExportPlan, ExportTargetFormat } from "@/services/exportApi";

interface ExportPlanCardProps {
	plan: ExportPlan;
	isExecuting: boolean;
	onFormatChange?: (newFormat: ExportTargetFormat) => void;
	onStartAgentRun: () => void;
	onDirectExecute: () => void;
	onDismiss: () => void;
}

const FORMAT_LABELS: Record<ExportTargetFormat, string> = {
	dxf: "AutoCAD DXF (.dxf)",
	revit: "Revit BIM (.json)",
	ifc: "IFC4 Model (.ifc)",
	xlsx: "Excel BoQ (.xlsx)",
	csv: "Tabular Inventory (.csv)",
	json: "Canonical JSON (.json)",
	pdf: "Engineering Report (.pdf)",
};

export const ExportPlanCard: React.FC<ExportPlanCardProps> = ({
	plan,
	isExecuting,
	onFormatChange,
	onStartAgentRun,
	onDirectExecute,
	onDismiss,
}) => {
	const isLossless = plan.mapping_status === "LOSSLESS";
	const isLossy = plan.mapping_status === "LOSSY";

	return (
		<div className="rounded-2xl border border-secondary/40 bg-card/90 backdrop-blur-md p-5 shadow-xl transition-all duration-200 animate-in fade-in-50">
			{/* Header */}
			<div className="flex items-start justify-between gap-3 border-b border-border/50 pb-3.5 mb-4">
				<div className="flex items-center gap-3">
					<div className="w-10 h-10 rounded-xl bg-secondary/15 border border-secondary/30 flex items-center justify-center text-secondary shrink-0">
						<FileCode2 className="h-5 w-5" />
					</div>
					<div>
						<div className="flex items-center gap-2 flex-wrap">
							<h3 className="text-sm font-bold text-foreground">
								Engineering Export Plan
							</h3>
							<Badge
								variant="outline"
								className={
									isLossless
										? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px]"
										: isLossy
											? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 text-[10px]"
											: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30 text-[10px]"
								}
							>
								{plan.mapping_status}
							</Badge>
						</div>
						<p className="text-xs text-muted-foreground mt-0.5">
							Target Project: <span className="font-mono text-foreground">{plan.project_id}</span> • Revision: <span className="font-mono font-semibold text-secondary">{plan.expected_revision}</span>
						</p>
					</div>
				</div>

				<Button
					variant="ghost"
					size="icon"
					className="h-7 w-7 text-muted-foreground hover:text-foreground -mr-1"
					onClick={onDismiss}
					disabled={isExecuting}
				>
					<X className="h-4 w-4" />
				</Button>
			</div>

			{/* Format Selector Pills */}
			{onFormatChange && (
				<div className="mb-4">
					<span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider block mb-2">
						Target Engineering Format
					</span>
					<div className="flex flex-wrap gap-1.5">
						{(Object.keys(FORMAT_LABELS) as ExportTargetFormat[]).map((fmt) => (
							<button
								key={fmt}
								type="button"
								onClick={() => onFormatChange(fmt)}
								disabled={isExecuting}
								className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
									plan.target_format === fmt
										? "bg-secondary text-secondary-foreground border-secondary font-semibold shadow-sm"
										: "bg-background/60 hover:bg-muted/80 text-muted-foreground border-border"
								}`}
							>
								{fmt.toUpperCase()}
							</button>
						))}
					</div>
				</div>
			)}

			{/* Entity Metrics Grid */}
			<div className="grid grid-cols-3 gap-2.5 mb-4">
				<div className="p-2.5 rounded-xl border border-border/60 bg-muted/20 text-center">
					<div className="text-base font-bold text-foreground">
						{plan.estimated_devices}
					</div>
					<div className="text-[11px] text-muted-foreground flex items-center justify-center gap-1 mt-0.5">
						<Layers className="h-3 w-3" />
						Devices
					</div>
				</div>

				<div className="p-2.5 rounded-xl border border-border/60 bg-muted/20 text-center">
					<div className="text-base font-bold text-foreground">
						{plan.estimated_connections}
					</div>
					<div className="text-[11px] text-muted-foreground flex items-center justify-center gap-1 mt-0.5">
						<Info className="h-3 w-3" />
						Circuits
					</div>
				</div>

				<div className="p-2.5 rounded-xl border border-border/60 bg-muted/20 text-center">
					<div className="text-base font-bold text-foreground">
						{plan.estimated_rooms}
					</div>
					<div className="text-[11px] text-muted-foreground flex items-center justify-center gap-1 mt-0.5">
						<CheckCircle2 className="h-3 w-3" />
						Rooms
					</div>
				</div>
			</div>

			{/* Warnings / Loss Information */}
			{plan.mapping_report.warnings.length > 0 && (
				<div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-xs mb-4 flex items-start gap-2">
					<AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-500" />
					<div className="space-y-1">
						{plan.mapping_report.warnings.map((w) => (
							<div key={w}>{w}</div>
						))}
					</div>
				</div>
			)}

			{/* Policy Information Footer */}
			<div className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-muted/40 border border-border/40 text-xs mb-4">
				<div className="flex items-center gap-2 text-muted-foreground">
					{plan.required_policy === "AUTO_APPROVED" ? (
						<ShieldCheck className="h-4 w-4 text-emerald-500" />
					) : (
						<ShieldAlert className="h-4 w-4 text-amber-500" />
					)}
					<span>Policy Gate: <strong className="text-foreground">{plan.required_policy}</strong></span>
				</div>
				<span className="text-[11px] text-muted-foreground">Immutable OCC Check</span>
			</div>

			{/* Actions */}
			<div className="flex items-center justify-end gap-2 pt-1">
				<Button
					variant="outline"
					size="sm"
					onClick={onDirectExecute}
					disabled={isExecuting}
					className="text-xs gap-1.5"
				>
					<Download className="h-3.5 w-3.5" />
					Direct Export
				</Button>

				<Button
					size="sm"
					onClick={onStartAgentRun}
					disabled={isExecuting}
					className="text-xs bg-secondary hover:bg-secondary/90 text-secondary-foreground gap-1.5 shadow-sm"
				>
					<Sparkles className="h-3.5 w-3.5" />
					Start Governed Run
					<ArrowRight className="h-3.5 w-3.5 ml-0.5" />
				</Button>
			</div>
		</div>
	);
};
