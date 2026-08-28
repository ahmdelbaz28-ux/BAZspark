import { describe, expect, it } from "vitest";
import { calculate, useClientMode, useTestMode } from "../index";
import type { EngineeringInputs } from "../index";

const smokeInputs: EngineeringInputs = { tab: "smoke", ceilingHeightM: 3.0 };
const voltageInputs: EngineeringInputs = { tab: "voltage", currentA: 10, lengthM: 50, awgGauge: "12" };

describe("engineering-calc package — index.ts entry point", () => {
	it("should calculate voltage drop in client mode", async () => {
		useClientMode();
		const result = await calculate(voltageInputs);
		expect(result.success).toBe(true);
		expect(result.voltageDropVolts).toBeDefined();
		expect(result.voltageDropPct).toBeDefined();
	});

	it("should return failure for unsupported client calculations", async () => {
		useClientMode();
		const result = await calculate(smokeInputs);
		expect(result.success).toBe(false);
		expect(result.message).toContain("not yet implemented");
	});

	it("should calculate with in-memory adapter", async () => {
		useTestMode();
		const result = await calculate(smokeInputs);
		expect(result.success).toBe(true);
		expect(result.spacingMeters).toBeDefined();
		expect(result.spacingMeters).toBe(9.2);
	});
});
