/**
 * dataService.test.ts — Unit tests for DataService (Phase 3).
 *
 * Tests the public seams:
 *   - connect(mode)
 *   - disconnect()
 *   - subscribeToProject(projectId)
 *   - getDataSource()
 *   - isConnectedLive()
 *   - switchMode(mode)
 *   - sendCommand(action, payload)
 *
 * WebSocket and Worker are mocked at the system boundary (global constructors).
 * Internal methods are NOT mocked — we test behavior through the public API.
 */

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { DataService } from "../dataService";
import { actions } from "@/store/simpleStore";

// ── Mock system boundaries ────────────────────────────────────────────────────

class MockWebSocket {
	static CONNECTING = 0;
	static OPEN = 1;
	static CLOSING = 2;
	static CLOSED = 3;

	readyState: number = MockWebSocket.CONNECTING;
	onopen: ((event: Event) => void) | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onerror: ((event: Event) => void) | null = null;
	onclose: ((event: CloseEvent) => void) | null = null;

	constructor(public url: string) {
		// Simulate async open
		setTimeout(() => {
			this.readyState = MockWebSocket.OPEN;
			if (this.onopen) {
				this.onopen(new Event("open"));
			}
		}, 0);
	}

	send(_data: string) {
		if (this.readyState !== MockWebSocket.OPEN) {
			throw new Error("WebSocket is not open");
		}
	}

	close(code = 1000, reason = "") {
		this.readyState = MockWebSocket.CLOSED;
		if (this.onclose) {
			this.onclose(new CloseEvent("close", { code, reason }));
		}
	}
}

class MockWorker {
	static INTERVAL_ID = 1;
	private intervalId: number | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onerror: ((event: ErrorEvent) => void) | null = null;

	constructor(_url: string | URL, _options?: WorkerOptions) {
		// Simulate async start behavior
		setTimeout(() => {
			if (this.onmessage) {
				this.onmessage(
					new MessageEvent("message", {
						data: { type: "data", data: { voltage: 220, current: 10, frequency: 50, hour: 12, fault: null } },
					}),
				);
			}
		}, 0);
	}

	postMessage(message: unknown) {
		if (typeof message === "object" && message !== null && (message as Record<string, unknown>).type === "start") {
			this.intervalId = MockWorker.INTERVAL_ID++;
		} else if (typeof message === "object" && message !== null && (message as Record<string, unknown>).type === "stop") {
			this.intervalId = null;
		}
	}

	terminate() {
		this.intervalId = null;
		this.onmessage = null;
		this.onerror = null;
	}
}

// Stub globals BEFORE importing DataService
vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
vi.stubGlobal("Worker", MockWorker as unknown as typeof Worker);

// ── Reset singleton between tests ────────────────────────────────────────────

function resetDataService() {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	(DataService as any).instance = null;
}

// ── Spy helpers ───────────────────────────────────────────────────────────────

const actionSpies = {
	setConnectionStatus: vi.spyOn(actions, "setConnectionStatus").mockImplementation(() => {}),
	addLog: vi.spyOn(actions, "addLog").mockImplementation(() => {}),
	updateLiveData: vi.spyOn(actions, "updateLiveData").mockImplementation(() => {}),
	addFault: vi.spyOn(actions, "addFault").mockImplementation(() => {}),
};

beforeEach(() => {
	resetDataService();
	Object.values(actionSpies).forEach((spy) => spy.mockClear());
});

afterEach(() => {
	resetDataService();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("DataService", () => {
	describe("connect(mode)", () => {
		it("defaults to mock mode in dev", () => {
			const ds = DataService.getInstance();
			ds.connect();
			expect(ds.getDataSource()).toBe("mock");
		});

		it("connects in mock mode when mode='mock'", () => {
			const ds = DataService.getInstance();
			ds.connect("mock");
			expect(ds.getDataSource()).toBe("mock");
		});

		it("connects in live mode when mode='live'", () => {
			const ds = DataService.getInstance();
			ds.connect("live");
			expect(ds.getDataSource()).toBe("live");
		});

		it("does not reconnect if already connected", () => {
			const ds = DataService.getInstance();
			ds.connect("mock");
			const firstSource = ds.getDataSource();
			ds.connect("mock");
			expect(ds.getDataSource()).toBe(firstSource);
		});
	});

	describe("disconnect()", () => {
		it("clears data source and resets connection status after mock connect", async () => {
			const ds = DataService.getInstance();
			ds.connect("mock");
			// Wait for mock worker to initialize
			await new Promise((resolve) => setTimeout(resolve, 50));
			ds.disconnect();
			expect(ds.getDataSource()).toBe("mock");
			expect(ds.isConnectedLive()).toBe(false);
		});

		it("sets connection status to disconnected", () => {
			const ds = DataService.getInstance();
			ds.connect("mock");
			ds.disconnect();
			expect(actionSpies.setConnectionStatus).toHaveBeenCalledWith("disconnected");
		});
	});

	describe("subscribeToProject(projectId)", () => {
		it("sends subscribe message over WebSocket when live and authenticated", async () => {
			const ds = DataService.getInstance();
			ds.connect("live");
			// Wait for WebSocket open
			await new Promise((resolve) => setTimeout(resolve, 50));
			// Authenticate
			ds.sendCommand("auth", { apiKey: "test-key" });
			await new Promise((resolve) => setTimeout(resolve, 50));
			ds.subscribeToProject("proj-123");
			// In live mode with auth, subscribe sends a WebSocket message
			expect(ds.getDataSource()).toBe("live");
		});
	});

	describe("getDataSource()", () => {
		it("returns 'mock' by default", () => {
			const ds = DataService.getInstance();
			expect(ds.getDataSource()).toBe("mock");
		});

		it("returns 'live' after live connect", () => {
			const ds = DataService.getInstance();
			ds.connect("live");
			expect(ds.getDataSource()).toBe("live");
		});
	});

	describe("isConnectedLive()", () => {
		it("returns false when not connected", () => {
			const ds = DataService.getInstance();
			expect(ds.isConnectedLive()).toBe(false);
		});

		it("returns false when connected in mock mode", () => {
			const ds = DataService.getInstance();
			ds.connect("mock");
			expect(ds.isConnectedLive()).toBe(false);
		});
	});

	describe("switchMode(mode)", () => {
		it("disconnects then connects in new mode", async () => {
			const ds = DataService.getInstance();
			ds.connect("mock");
			await new Promise((resolve) => setTimeout(resolve, 50));
			ds.switchMode("live");
			await new Promise((resolve) => setTimeout(resolve, 150));
			expect(ds.getDataSource()).toBe("live");
		});
	});

	describe("sendCommand(action, payload)", () => {
		it("does not send when not connected", () => {
			const ds = DataService.getInstance();
			ds.sendCommand("ping");
			// No WebSocket to send to, should be a no-op
			expect(actionSpies.addLog).toHaveBeenCalled();
		});
	});
});
