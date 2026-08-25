/**
 * RemoteCADSessionBar.tsx — B4 Remote CAD Session control strip.
 *
 * Shows the live desktop-agent session status (BazSparkAutoCADBridge over
 * named pipes), lets the user queue a native AutoCAD command, and pulls an
 * inline screenshot so they can visually verify the outcome.
 */

import { Camera, Loader2, MonitorCheck, MonitorX, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	cadRemoteApi,
	type CaptureScreenResponse,
	type RemoteStatusResponse,
} from "@/services/cadRemoteApi";

export function RemoteCADSessionBar() {
	const [status, setStatus] = useState<RemoteStatusResponse | null>(null);
	const [checking, setChecking] = useState(true);
	const [command, setCommand] = useState("");
	const [sending, setSending] = useState(false);
	const [capturing, setCapturing] = useState(false);
	const [screenshot, setScreenshot] = useState<CaptureScreenResponse | null>(null);

	const refreshStatus = useCallback(async () => {
		setChecking(true);
		try {
			const res = await cadRemoteApi.getRemoteStatus();
			setStatus(res);
		} catch {
			setStatus(null);
		} finally {
			setChecking(false);
		}
	}, []);

	useEffect(() => {
		void refreshStatus();
	}, [refreshStatus]);

	const agentConnected = status?.agent_connected === true;

	const sendCommand = async () => {
		if (!command.trim()) return;
		setSending(true);
		try {
			await cadRemoteApi.sendNativeCommand(command.trim());
			toast.success(`Command queued: ${command.trim()}`);
			setCommand("");
		} catch (err) {
			toast.error(
				`Send failed: ${err instanceof Error ? err.message : "Unknown error"}`,
			);
		} finally {
			setSending(false);
		}
	};

	const capture = async () => {
		setCapturing(true);
		try {
			const shot = await cadRemoteApi.captureScreen();
			setScreenshot(shot);
			if (!shot.success) {
				toast.warning(shot.message || "Capture returned no image");
			}
		} catch (err) {
			toast.error(
				`Capture failed: ${err instanceof Error ? err.message : "Unknown error"}`,
			);
		} finally {
			setCapturing(false);
		}
	};

	return (
		<div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
			<div className="flex flex-wrap items-center gap-3">
				{checking ? (
					<Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
				) : agentConnected ? (
					<span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-600">
						<MonitorCheck className="h-4 w-4" />
						Desktop agent connected
					</span>
				) : (
					<span className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
						<MonitorX className="h-4 w-4" />
						No desktop agent
					</span>
				)}

				<div className="ml-auto flex items-center gap-2">
					<div className="relative w-72 max-w-full">
						<Terminal className="pointer-events-none absolute top-2.5 left-2.5 h-4 w-4 text-muted-foreground" />
						<Input
							value={command}
							onChange={(e) => setCommand(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !sending) void sendCommand();
							}}
							placeholder={agentConnected ? "_.LINE 0,0 100,100" : "Start local_agent.py to enable"}
							disabled={!agentConnected || sending}
							className="pl-8"
						/>
					</div>
					<Button size="sm" onClick={() => void sendCommand()} disabled={!agentConnected || sending}>
						{sending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Queue"}
					</Button>
					<Button
						size="sm"
						variant="outline"
						onClick={() => void capture()}
						disabled={!agentConnected || capturing}
					>
						{capturing ? (
							<Loader2 className="h-4 w-4 animate-spin" />
						) : (
							<Camera className="h-4 w-4" />
						)}
						Screenshot
					</Button>
				</div>
			</div>

			{screenshot?.image_base64 ? (
				<img
					src={`data:image/png;base64,${screenshot.image_base64}`}
					alt="AutoCAD window capture"
					className="max-h-56 w-full rounded border object-contain"
				/>
			) : null}

			{!agentConnected && !checking && status?.message ? (
				<p className="text-xs text-muted-foreground">{status.message}</p>
			) : null}
		</div>
	);
}
