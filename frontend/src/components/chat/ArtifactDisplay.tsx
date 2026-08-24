/**
 * ArtifactDisplay.tsx — Generic Artifact Presentation Surface (Phase 2).
 *
 * Displays calculation reports and drawing artifacts produced by backend runs
 * with format, size, status, and download/preview metadata.
 */
import {
	CheckCircle2,
	Download,
	FileCode,
	FileSpreadsheet,
	FileText,
	HardDrive,
} from "lucide-react";
import type React from "react";

export interface ProducedArtifact {
	artifact_id: string;
	filename: string;
	format: "PDF" | "DXF" | "JSON" | "IFC" | "RVT" | string;
	size_bytes?: number;
	status: "ready" | "generating" | "failed";
	download_url?: string;
	created_at?: string;
}

interface ArtifactDisplayProps {
	artifacts: ProducedArtifact[];
}

function formatBytes(bytes?: number): string {
	if (!bytes) return "—";
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFormatIcon(format: string) {
	const fmt = format.toUpperCase();
	if (fmt === "PDF") return <FileText className="h-4 w-4 text-red-400" />;
	if (fmt === "DXF" || fmt === "RVT" || fmt === "IFC")
		return <FileCode className="h-4 w-4 text-cyan-400" />;
	if (fmt === "JSON" || fmt === "CSV" || fmt === "XLSX")
		return <FileSpreadsheet className="h-4 w-4 text-emerald-400" />;
	return <HardDrive className="h-4 w-4 text-secondary" />;
}

export const ArtifactDisplay: React.FC<ArtifactDisplayProps> = ({
	artifacts,
}) => {
	if (!artifacts || artifacts.length === 0) return null;

	return (
		<div
			className="rounded-2xl border border-border/80 bg-card/60 backdrop-blur-md p-4 space-y-3 shadow-md"
			data-testid="artifact-display-container"
		>
			<div className="flex items-center justify-between border-b border-border/40 pb-2">
				<span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
					<CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
					Produced Artifacts ({artifacts.length})
				</span>
			</div>

			<div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
				{artifacts.map((art) => (
					<div
						key={art.artifact_id}
						className="flex items-center justify-between p-3 rounded-xl border border-border/50 bg-card hover:border-secondary/40 transition-colors"
					>
						<div className="flex items-center gap-2.5 min-w-0">
							<div className="w-8 h-8 rounded-lg bg-muted/60 flex items-center justify-center shrink-0">
								{getFormatIcon(art.format)}
							</div>
							<div className="min-w-0">
								<p
									className="text-xs font-semibold text-foreground truncate"
									title={art.filename}
								>
									{art.filename}
								</p>
								<div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground mt-0.5">
									<span className="px-1.5 py-0.2 rounded bg-muted text-foreground">
										{art.format.toUpperCase()}
									</span>
									<span>{formatBytes(art.size_bytes)}</span>
								</div>
							</div>
						</div>

						{art.download_url && (
							<a
								href={art.download_url}
								download={art.filename}
								target="_blank"
								rel="noreferrer"
								className="h-8 w-8 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
								title={`Download ${art.filename}`}
								aria-label={`Download ${art.filename}`}
							>
								<Download className="h-3.5 w-3.5" />
							</a>
						)}
					</div>
				))}
			</div>
		</div>
	);
};
