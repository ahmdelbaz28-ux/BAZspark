import { describe, expect, it } from "vitest";
import { useClientMode } from "../index";

describe("engineering-calc package — client adapter", () => {
	it("should calculate voltage drop client-side", async () => {
		useClientMode();
		const { calculate } = await import("../index");
		const result = await calculate({
			tab: "voltage",
			currentA: 10,
			lengthM: 50,
			awgGauge: "12",
		});
		expect(result.success).toBe(true);
		expect(result.voltageDropVolts).toBeGreaterThan(0);
		expect(result.voltageDropPct).toBeGreaterThan(0);
	});

	it("should fail gracefully for unsupported tabs in client mode", async () => {
		useClientMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "smoke", ceilingHeightM: 3 });
		expect(result.success).toBe(false);
		expect(result.message).toBeDefined();
	});
});
