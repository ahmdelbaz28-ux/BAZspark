import type React from "react";
import { memo } from "react";
import "@/styles/shell.css";

interface StatusBarProps {
	backendUrl: string;
	isConnected: boolean;
	environment: string;
}

const APP_VERSION = "v1.56.0";

const StatusBar: React.FC<StatusBarProps> = memo(
	({ backendUrl, isConnected, environment }) => {
		return (
			<footer
				className="shell-statusbar h-6 flex items-center px-3 gap-2 shrink-0 bg-card border-t border-border text-[11px] font-mono text-muted-foreground select-none"
				data-onboarding="status-bar"
				role="contentinfo"
				aria-label="Application status"
			>
				<span className="shell-version text-foreground font-semibold">BAZSPARK {APP_VERSION}</span>

				<span className="text-border">|</span>

				<span
					className="shell-backend-url truncate max-w-[28vw] tabular-nums"
					title={backendUrl}
					aria-label={`Backend URL: ${backendUrl}`}
				>
					API: {backendUrl}
				</span>

				<span className="text-border hidden sm:inline">|</span>

				<span
					className="shell-env capitalize hidden sm:inline"
					aria-label={`Environment: ${environment}`}
				>
					ENV: {environment}
				</span>

				<span className="text-border hidden md:inline">|</span>

				<span className="hidden md:inline text-primary font-medium">
					STD: NFPA 72 (2022)
				</span>

				<div className="flex-1" />

				<span className="hidden lg:inline text-muted-foreground text-[10px]">
					Ctrl+K Command | Ctrl+J Copilot | F1 Help
				</span>

				<span className="text-border hidden lg:inline">|</span>

				<div
					className="flex items-center gap-1.5"
					role="status"
					aria-live="polite"
					aria-label={
						isConnected ? "Connected to backend" : "Disconnected from backend"
					}
				>
					<span
						className={`h-2 w-2 rounded-full ${isConnected ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]" : "bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.5)]"}`}
						aria-hidden="true"
					/>
					<span className={isConnected ? "text-emerald-400 font-medium" : "text-amber-400 font-medium"}>
						{isConnected ? "SYSTEM READY" : "OFFLINE"}
					</span>
				</div>
			</footer>
		);
	},
);

StatusBar.displayName = "StatusBar";

export default StatusBar;
