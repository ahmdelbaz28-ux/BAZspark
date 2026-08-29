import { beforeEach, describe, expect, it, vi } from "vitest";
import { useServerMode } from "../index";
import { qomnApi, qomnExtendedApi } from "@/services/fullApi";

// Mock the fullApi module so HTTP adapter tests run without a live backend.
// Follows the same vi.mock pattern used in useAgentRun.test.ts.
vi.mock("@/services/fullApi", () => ({
	qomnApi: {
		smokeSpacing: vi.fn(),
		heatSpacing: vi.fn(),
		battery: vi.fn(),
		voltageDrop: vi.fn(),
		getPhysicsGuards: vi.fn(),
	},
	qomnExtendedApi: {
		placeDetectors: vi.fn(),
		placeDuct: vi.fn(),
		runGoldenTests: vi.fn(),
	},
}));

describe("engineering-calc package — http adapter (mocked API)", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should calculate smoke spacing via HTTP", async () => {
		vi.mocked(qomnApi.smokeSpacing).mockResolvedValue({ spacing_meters: 11.5 });
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "smoke", ceilingHeightM: 3 });
		expect(result.success).toBe(true);
		expect(result.spacingMeters).toBe(11.5);
		expect(qomnApi.smokeSpacing).toHaveBeenCalledWith({ ceiling_height_m: 3 });
	});

	it("should calculate heat spacing via HTTP", async () => {
		vi.mocked(qomnApi.heatSpacing).mockResolvedValue({ spacing_meters: 6.5 });
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "heat", ceilingHeightM: 3, areaPerDetectorM2: 20 });
		expect(result.success).toBe(true);
		expect(result.spacingMeters).toBe(6.5);
		expect(qomnApi.heatSpacing).toHaveBeenCalledWith({
			ceiling_height_m: 3,
			area_per_detector_m2: 20,
		});
	});

	it("should calculate battery via HTTP", async () => {
		vi.mocked(qomnApi.battery).mockResolvedValue({ battery_capacity_ah: 24.5 });
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "battery", standbyLoadA: 0.5, alarmLoadA: 1.0 });
		expect(result.success).toBe(true);
		expect(result.batteryCapacityAh).toBe(24.5);
		expect(qomnApi.battery).toHaveBeenCalledWith({
			standby_load_a: 0.5,
			alarm_load_a: 1.0,
			standby_hours: undefined,
			alarm_minutes: undefined,
			safety_factor: undefined,
			efficiency: undefined,
		});
	});

	it("should forward safety_factor and efficiency to HTTP API", async () => {
		vi.mocked(qomnApi.battery).mockResolvedValue({ battery_capacity_ah: 32.8 });
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({
			tab: "battery",
			standbyLoadA: 0.8,
			alarmLoadA: 2.5,
			standbyHours: 60,
			alarmMinutes: 15,
			safetyFactor: 1.4,
			efficiency: 0.85,
		});
		expect(result.success).toBe(true);
		expect(result.batteryCapacityAh).toBe(32.8);
		expect(qomnApi.battery).toHaveBeenCalledWith({
			standby_load_a: 0.8,
			alarm_load_a: 2.5,
			standby_hours: 60,
			alarm_minutes: 15,
			safety_factor: 1.4,
			efficiency: 0.85,
		});
	});

	it("should reject invalid inputs early in HTTP mode without calling backend", async () => {
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({
			tab: "battery",
			standbyLoadA: -1,
			alarmLoadA: 1.0,
		});
		expect(result.success).toBe(false);
		expect(result.message).toBe("Validation failed");
		expect(qomnApi.battery).not.toHaveBeenCalled();
	});

	it("should calculate detector placement via HTTP", async () => {
		const mockLayout = { placed: 8, compliant: true };
		vi.mocked(qomnExtendedApi.placeDetectors).mockResolvedValue(mockLayout);
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "detectors", roomAreaM2: 100, ceilingHeightM: 3 });
		expect(result.success).toBe(true);
		expect(result.detectorLayout).toBeDefined();
		expect(qomnExtendedApi.placeDetectors).toHaveBeenCalledWith({
			room_area_m2: 100,
			ceiling_height_m: 3,
			detector_type: undefined,
		});
	});

	it("should calculate duct placement via HTTP", async () => {
		const mockDuct = { placed: 3, compliant: true };
		vi.mocked(qomnExtendedApi.placeDuct).mockResolvedValue(mockDuct);
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "duct", ductWidthM: 0.3 });
		expect(result.success).toBe(true);
		expect(result.ductResults).toBeDefined();
		expect(result.ductResults).toEqual(mockDuct);
		expect(qomnExtendedApi.placeDuct).toHaveBeenCalledWith({
			duct_width_m: 0.3,
			duct_velocity_mps: undefined,
			airflow_direction: undefined,
		});
	});
});
