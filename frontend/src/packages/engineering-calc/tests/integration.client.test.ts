import { describe, expect, it } from "vitest";
import { calculate, getPhysicsGuards, useClientMode } from "../index";

describe("engineering-calc package — client adapter", () => {
	it("should calculate voltage drop client-side", async () => {
		useClientMode();
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

	it("should calculate battery capacity client-side with safetyFactor and efficiency", async () => {
		useClientMode();
		const result = await calculate({
			tab: "battery",
			standbyLoadA: 0.5,
			alarmLoadA: 2.0,
			standbyHours: 24,
			alarmMinutes: 5,
			safetyFactor: 1.25,
			efficiency: 0.9,
		});
		expect(result.success).toBe(true);
		expect(result.batteryCapacityAh).toBeDefined();
		expect(result.batteryCapacityAh).toBeGreaterThan(0);
		expect(result.data).toBeDefined();
	});

	it("should reject invalid battery inputs early in client mode without calculating", async () => {
		useClientMode();
		const result = await calculate({
			tab: "battery",
			standbyLoadA: -0.5,
			alarmLoadA: 2.0,
		});
		expect(result.success).toBe(false);
		expect(result.message).toBe("Validation failed");
	});

	it("should return complete physics guards including battery fields", async () => {
		useClientMode();
		const guards = await getPhysicsGuards();
		expect(guards.safetyFactor).toBeDefined();
		expect(guards.efficiency).toBeDefined();
		expect(guards.standbyHours).toBeDefined();
		expect(guards.alarmMinutes).toBeDefined();
	});

	it("should fail gracefully for unsupported tabs in client mode", async () => {
		useClientMode();
		const result = await calculate({ tab: "smoke", ceilingHeightM: 3 });
		expect(result.success).toBe(false);
		expect(result.message).toBeDefined();
	});
});
