/**
 * cadRemoteApi.test.ts — Contract tests for the B4 remote CAD session API.
 *
 * Verifies each method targets the agent-backed /autocad endpoints with the
 * right verb/payload and passes responses through untouched.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiCallMock = vi.fn();

vi.mock("@/services/fullApi", () => ({
	apiCall: (...args: unknown[]) => apiCallMock(...args),
}));

import { cadRemoteApi } from "../cadRemoteApi";

describe("cadRemoteApi", () => {
	beforeEach(() => {
		apiCallMock.mockReset();
		apiCallMock.mockResolvedValue({ success: true });
	});

	it("getRemoteStatus hits GET /autocad/remote/status", async () => {
		const res = await cadRemoteApi.getRemoteStatus();
		expect(apiCallMock).toHaveBeenCalledWith("/autocad/remote/status", {
			method: "GET",
		});
		expect(res).toEqual({ success: true });
	});

	it("sendNativeCommand posts JSON body with command_string", async () => {
		await cadRemoteApi.sendNativeCommand("_.ZOOM _E");
		const [path, init] = apiCallMock.mock.calls[0];
		expect(path).toBe("/autocad/send_command");
		expect(init.method).toBe("POST");
		expect(JSON.parse(init.body)).toEqual({ command_string: "_.ZOOM _E" });
	});

	it("captureScreen hits GET /autocad/capture_screen", async () => {
		apiCallMock.mockResolvedValue({
			success: true,
			image_base64: "QUJD",
			format: "png",
		});
		const res = await cadRemoteApi.captureScreen();
		expect(apiCallMock).toHaveBeenCalledWith("/autocad/capture_screen", {
			method: "GET",
		});
		expect(res.image_base64).toBe("QUJD");
	});
});
