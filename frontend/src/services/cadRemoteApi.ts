/**
 * cadRemoteApi.ts — B4 Remote CAD Session API surface.
 *
 * Talks to the agent-backed /api/v1/autocad endpoints (send_command,
 * capture_screen, remote/status) that execute on the user's desktop via
 * the BazSparkAutoCADBridge named-pipe agent.
 */

import { apiCall } from "@/services/fullApi";

export interface RemoteStatusResponse {
	success: boolean;
	agent_connected: boolean;
	message?: string;
	session?: Record<string, unknown>;
}

export interface NativeCommandResponse {
	success: boolean;
	queued?: boolean;
	command?: string;
	error?: string;
}

export interface CaptureScreenResponse {
	success: boolean;
	image_base64?: string | null;
	format?: string;
	message?: string | null;
}

export const cadRemoteApi = {
	/** GET /autocad/remote/status */
	getRemoteStatus: () =>
		apiCall<RemoteStatusResponse>("/autocad/remote/status", { method: "GET" }),

	/** POST /autocad/send_command — native command passthrough (async). */
	sendNativeCommand: (command_string: string) =>
		apiCall<NativeCommandResponse>("/autocad/send_command", {
			method: "POST",
			body: JSON.stringify({ command_string }),
		}),

	/** GET /autocad/capture_screen — base64 PNG of the AutoCAD window. */
	captureScreen: () =>
		apiCall<CaptureScreenResponse>("/autocad/capture_screen", { method: "GET" }),
};
