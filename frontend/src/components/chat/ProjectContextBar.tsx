/**
 * ProjectContextBar.tsx — Project & Model Context Header (Phase 2).
 *
 * Displays the current engineering project ID, revision, active AI provider/model,
 * and live connection health status at the top of the Chat Control Center.
 */
import {
	Cpu,
	FolderGit2,
	RotateCcw,
	Settings,
	Trash2,
	Zap,
} from "lucide-react";
import type React from "react";
import { Link } from "react-router";
import { useAgentSettings } from "@/contexts/AgentSettingsContext";
import { useActiveProject } from "@/contexts/ProjectContext";

interface ProjectContextBarProps {
	projectId?: string;
	projectRevision?: number;
	isConnected: boolean;
	isReconnecting: boolean;
	onClearChat: () => void;
	onNewRun?: () => void;
}

export const ProjectContextBar: React.FC<ProjectContextBarProps> = ({
	projectId: propProjectId,
	projectRevision: propRevision,
	isConnected,
	isReconnecting,
	onClearChat,
	onNewRun,
}) => {
	const { settings } = useAgentSettings();
	const { activeProjectId, activeRevision } = useActiveProject();
	const projectId = propProjectId || activeProjectId;
	const projectRevision = propRevision !== undefined ? propRevision : activeRevision;

	const providerName = settings.llm.provider.toUpperCase();
	const modelName = settings.llm.model;

	return (
		<div
			className="h-14 border-b border-border flex items-center justify-between px-6 bg-card/80 backdrop-blur-md shrink-0"
			data-testid="project-context-bar"
		>
			{/* Left: Brand / Title */}
			<div className="flex items-center gap-3">
				<div className="w-8 h-8 rounded-lg bg-gradient-to-br from-secondary to-secondary/60 flex items-center justify-center border border-secondary/50 shadow-sm">
					<Zap className="h-4 w-4 text-secondary-foreground" />
				</div>
				<div>
					<div className="flex items-center gap-2">
						<h1 className="font-semibold text-sm text-foreground">
							FireAI Control Center
						</h1>
						<span className="text-[10px] font-mono font-semibold px-2 py-0.2 rounded bg-secondary/15 text-secondary border border-secondary/30">
							AI-First
						</span>
					</div>
					<p className="text-[10px] text-muted-foreground">
						Deterministic Engineering Spine · NFPA 72 PE Gated
					</p>
				</div>
			</div>

			{/* Center: Project & Model Context Chips */}
			<div className="hidden md:flex items-center gap-2">
				{/* Project Chip */}
				<div
					className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/40 border border-border/50 text-xs text-muted-foreground"
					title="Active Engineering Project"
				>
					<FolderGit2 className="h-3.5 w-3.5 text-secondary" />
					<span className="font-medium text-foreground">{projectId}</span>
					<span className="font-mono text-[10px] text-muted-foreground">
						(Rev: {projectRevision})
					</span>
				</div>

				{/* Provider/Model Chip */}
				<div
					className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/40 border border-border/50 text-xs text-muted-foreground"
					title="Active AI Provider & Model"
				>
					<Cpu className="h-3.5 w-3.5 text-cyan-400" />
					<span className="font-medium text-foreground">{providerName}</span>
					<span className="font-mono text-[10px] text-muted-foreground truncate max-w-[120px]">
						{modelName}
					</span>
				</div>

				{/* Connection Health Indicator */}
				<div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/20 text-xs">
					<div
						className={`w-2 h-2 rounded-full ${
							isConnected
								? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"
								: isReconnecting
									? "bg-amber-500 animate-ping"
									: "bg-destructive"
						}`}
					/>
					<span className="text-[10px] font-mono text-muted-foreground">
						{isConnected
							? "Live WS"
							: isReconnecting
								? "Reconnecting…"
								: "Offline"}
					</span>
				</div>
			</div>

			{/* Right: Actions */}
			<div className="flex items-center gap-1.5">
				{onNewRun && (
					<button
						type="button"
						onClick={onNewRun}
						title="New Run"
						aria-label="New Engineering Run"
						className="h-8 px-2.5 rounded-lg border border-border flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
					>
						<RotateCcw className="h-3.5 w-3.5" />
						<span className="hidden sm:inline">Reset Run</span>
					</button>
				)}

				<button
					type="button"
					onClick={onClearChat}
					title="Clear conversation messages"
					aria-label="Clear chat"
					className="h-8 w-8 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
				>
					<Trash2 className="h-3.5 w-3.5" />
				</button>

				<Link
					to="/settings/ai-agents"
					title="AI Agent Settings"
					aria-label="Open AI Agent Settings"
					className="h-8 w-8 rounded-lg border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
				>
					<Settings className="h-3.5 w-3.5" />
				</Link>
			</div>
		</div>
	);
};
