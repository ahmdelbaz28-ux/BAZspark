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
		const connState = isConnected ? "online" : "offline";
		return (
			<footer
				className="shell-statusbar h-7 flex items-center px-4 gap-3 shrink-0"
				data-onboarding="status-bar"
				role="contentinfo"
				aria-label="Application status"
			>
				<span className="shell-version">BAZSPARK {APP_VERSION}</span>

				<hr className="shell-statusbar-separator" aria-orientation="vertical" />

				<span
					className="shell-backend-url truncate max-w-[40vw] tabular-nums"
					title={backendUrl}
					aria-label={`Backend URL: ${backendUrl}`}
				>
					{backendUrl}
				</span>

				<hr className="shell-statusbar-separator" aria-orientation="vertical" />

				<span
					className="shell-env capitalize"
					aria-label={`Environment: ${environment}`}
				>
					{environment}
				</span>

				<div className="flex-1" />

				<div
					className="flex items-center gap-1.5"
					role="status"
					aria-live="polite"
					aria-label={
						isConnected ? "Connected to backend" : "Disconnected from backend"
					}
				>
					<span
						className={`shell-status-conn-dot ${connState}`}
						aria-hidden="true"
					/>
					<span className={`shell-status-conn-label ${connState}`}>
						{isConnected ? "Connected" : "Disconnected"}
					</span>
				</div>
			</footer>
		);
	},
);

StatusBar.displayName = "StatusBar";

export default StatusBar;
