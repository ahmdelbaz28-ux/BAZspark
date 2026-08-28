import { describe, expect, it } from "vitest";
import { useServerMode } from "../index";

describe.skip("engineering-calc package — http adapter (requires backend)", () => {
	it("should calculate smoke spacing via HTTP", async () => {
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "smoke", ceilingHeightM: 3 });
		expect(result.success).toBe(true);
	});

	it("should calculate heat spacing via HTTP", async () => {
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "heat", ceilingHeightM: 3, areaPerDetectorM2: 20 });
		expect(result.success).toBe(true);
	});

	it("should calculate battery via HTTP", async () => {
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "battery", standbyLoadA: 0.5, alarmLoadA: 1.0 });
		expect(result.success).toBe(true);
	});

	it("should calculate detector placement via HTTP", async () => {
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "detectors", roomAreaM2: 100, ceilingHeightM: 3 });
		expect(result.success).toBe(true);
	});

	it("should calculate duct placement via HTTP", async () => {
		useServerMode();
		const { calculate } = await import("../index");
		const result = await calculate({ tab: "duct", ductWidthM: 0.3 });
		expect(result.success).toBe(true);
	});
});
