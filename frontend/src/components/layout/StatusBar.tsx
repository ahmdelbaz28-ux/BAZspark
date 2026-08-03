import type React from "react";
import { memo } from "react";

interface StatusBarProps {
        backendUrl: string;
        isConnected: boolean;
        environment: string;
}

const APP_VERSION = "v1.55.0";

const StatusBar: React.FC<StatusBarProps> = memo(({
        backendUrl,
        isConnected,
        environment,
}) => {
        return (
                <footer
                        className="h-7 bg-[#0a0e17] flex items-center px-4 gap-3 text-[11px] shrink-0 text-muted-foreground border-t border-white/10"
                        data-onboarding="status-bar"
                        role="contentinfo"
                        aria-label="Application status"
                >
                        <span className="font-medium text-cyan-400">BAZSPARK {APP_VERSION}</span>

                        <div className="h-3 w-px bg-white/10" role="separator" aria-orientation="vertical" />

                        <span
                                className="truncate max-w-[40vw] font-mono tabular-nums"
                                title={backendUrl}
                                aria-label={`Backend URL: ${backendUrl}`}
                        >
                                {backendUrl}
                        </span>

                        <div className="h-3 w-px bg-white/10" role="separator" aria-orientation="vertical" />

                        <span className="capitalize" aria-label={`Environment: ${environment}`}>
                                {environment}
                        </span>

                        <div className="flex-1" />

                        <div
                                className="flex items-center gap-1.5"
                                role="status"
                                aria-live="polite"
                                aria-label={isConnected ? "Connected to backend" : "Disconnected from backend"}
                        >
                                <span
                                        className={`h-1.5 w-1.5 rounded-full ${isConnected ? "bg-success" : "bg-slate-500"}`}
                                        aria-hidden="true"
                                />
                                <span className="tabular-nums">{isConnected ? "Connected" : "Disconnected"}</span>
                        </div>
                </footer>
        );
});

StatusBar.displayName = "StatusBar";

export default StatusBar;
