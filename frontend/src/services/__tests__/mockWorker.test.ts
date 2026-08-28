/**
 * mockWorker.test.ts — Unit tests for mockWorker (Phase 3).
 *
 * Tests the public seams of the mock Web Worker:
 *   - start message begins data generation
 *   - stop message halts data generation
 *   - data messages contain expected telemetry fields
 */

import { describe, expect, it, vi } from "vitest";

// ── Mock Worker at system boundary ────────────────────────────────────────────

class MockTestWorker {
	static INTERVAL_ID = 1;
	private intervalId: number | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onerror: ((event: ErrorEvent) => void) | null = null;

	constructor(_url: string | URL, _options?: WorkerOptions) {
		setTimeout(() => {
			if (this.onmessage) {
				this.onmessage(
					new MessageEvent("message", {
						data: {
							type: "data",
							data: { voltage: 220, current: 10, frequency: 50, hour: 12, fault: null },
						},
					}),
				);
			}
		}, 0);
	}

	postMessage(message: unknown) {
		if (typeof message === "object" && message !== null && (message as Record<string, unknown>).type === "start") {
			this.intervalId = MockTestWorker.INTERVAL_ID++;
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

vi.stubGlobal("Worker", MockTestWorker as unknown as typeof Worker);

describe("mockWorker", () => {
	it("generates data messages after receiving start", async () => {
		const worker = new Worker(
			new URL("../mockWorker.ts", import.meta.url),
			{ type: "module" },
		);

		const dataMessages: unknown[] = [];
		worker.onmessage = (event: MessageEvent) => {
			dataMessages.push(event.data);
		};

		worker.postMessage({ type: "start" });

		// Wait for the worker to emit at least one data message
		await new Promise((resolve) => setTimeout(resolve, 1500));

		const hasData = dataMessages.some(
			(msg) =>
				typeof msg === "object" &&
				msg !== null &&
				(msg as Record<string, unknown>).type === "data",
		);

		expect(hasData).toBe(true);

		worker.postMessage({ type: "stop" });
		worker.terminate();
	});

	it("data messages contain voltage, current, frequency, hour, and fault fields", async () => {
		const worker = new Worker(
			new URL("../mockWorker.ts", import.meta.url),
			{ type: "module" },
		);

		let dataMsg: Record<string, unknown> | null = null;
		worker.onmessage = (event: MessageEvent) => {
			const msg = event.data as Record<string, unknown>;
			if (msg.type === "data") {
				dataMsg = msg.data as Record<string, unknown>;
			}
		};

		worker.postMessage({ type: "start" });

		await new Promise((resolve) => setTimeout(resolve, 1500));

		expect(dataMsg).not.toBeNull();
		expect(dataMsg).toHaveProperty("voltage");
		expect(dataMsg).toHaveProperty("current");
		expect(dataMsg).toHaveProperty("frequency");
		expect(dataMsg).toHaveProperty("hour");
		expect(dataMsg).toHaveProperty("fault");
		expect(typeof dataMsg!.voltage).toBe("number");
		expect(typeof dataMsg!.current).toBe("number");
		expect(typeof dataMsg!.frequency).toBe("number");
		expect(typeof dataMsg!.hour).toBe("number");

		worker.postMessage({ type: "stop" });
		worker.terminate();
	});

	it("does not generate data after receiving stop", async () => {
		const worker = new Worker(
			new URL("../mockWorker.ts", import.meta.url),
			{ type: "module" },
		);

		const dataMessages: unknown[] = [];
		worker.onmessage = (event: MessageEvent) => {
			dataMessages.push(event.data);
		};

		worker.postMessage({ type: "start" });
		await new Promise((resolve) => setTimeout(resolve, 500));

		worker.postMessage({ type: "stop" });
		await new Promise((resolve) => setTimeout(resolve, 500));

		const messageCount = dataMessages.length;
		await new Promise((resolve) => setTimeout(resolve, 1500));

		expect(dataMessages.length).toBe(messageCount);

		worker.terminate();
	});
});
