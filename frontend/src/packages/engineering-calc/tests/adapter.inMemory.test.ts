import { describe, expect, it } from "vitest";
import { useTestMode } from "../index";

describe("engineering-calc package — in-memory adapter", () => {
	it("should return deterministic smoke spacing", async () => {
		useTestMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "smoke", ceilingHeightM: 3 });
		expect(result.success).toBe(true);
		expect(result.spacingMeters).toBe(9.2);
		expect(result.complianceStatus).toBe("COMPLIANT");
	});

	it("should return deterministic heat spacing", async () => {
		useTestMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "heat", ceilingHeightM: 3, areaPerDetectorM2: 20 });
		expect(result.success).toBe(true);
		expect(result.spacingMeters).toBe(6.5);
	});

	it("should return deterministic battery", async () => {
		useTestMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "battery", standbyLoadA: 0.5, alarmLoadA: 1.0 });
		expect(result.success).toBe(true);
		expect(result.batteryCapacityAh).toBe(24.5);
	});

	it("should return deterministic voltage drop", async () => {
		useTestMode();
		const { calculate } = await import("../index");
		const result = await calculate({
			tab: "voltage",
			currentA: 10,
			lengthM: 50,
			awgGauge: "12",
		});
		expect(result.success).toBe(true);
		expect(result.voltageDropVolts).toBe(0.8);
		expect(result.voltageDropPct).toBe(3.3);
	});

	it("should return deterministic detectors", async () => {
		useTestMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "detectors", roomAreaM2: 100, ceilingHeightM: 3 });
		expect(result.success).toBe(true);
		expect(result.detectorsRequired).toBe(8);
	});

	it("should return deterministic duct results", async () => {
		useTestMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "duct", ductWidthM: 0.3 });
		expect(result.success).toBe(true);
		expect(result.ductResults?.placed).toBe(3);
	});
});
