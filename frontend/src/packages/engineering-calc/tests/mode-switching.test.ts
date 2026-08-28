import { describe, expect, it } from "vitest";
import { useClientMode, useServerMode, useTestMode } from "../index";

describe("engineering-calc package — mode switching", () => {
	it("should switch to client mode", async () => {
		const { calculate } = await import("../index");
		useClientMode();
		const result = await calculate({ tab: "voltage", currentA: 10, lengthM: 50, awgGauge: "12" });
		expect(result.success).toBe(true);
	});

	it("should switch to test mode", async () => {
		const { calculate } = await import("../index");
		useTestMode();
		const result = await calculate({ tab: "battery", standbyLoadA: 0.5, alarmLoadA: 1.0 });
		expect(result.success).toBe(true);
		expect(result.batteryCapacityAh).toBe(24.5);
	});
});
